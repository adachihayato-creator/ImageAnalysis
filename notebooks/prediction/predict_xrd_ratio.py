"""Exploratory, film-grouped XRD ratio regression; no zero labels for unresolved peaks."""
from pathlib import Path
import sys,json,csv,hashlib
import numpy as np,cv2
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'notebooks/film_time_series'),str(ROOT/'notebooks/capture_repeatability')]
from analyze_sn10_xrd import features,WINDOWS
from analyze_repeatability import corners_and_bbox
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error
O=ROOT/'results/20261117/06_xrd_ratio_prediction';O.mkdir(parents=True,exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];LOW=[{'search':(12.25,13),'background':b} for b in [((11.5,11.8),(13.1,13.3)),((12,12.2),(13.05,13.2)),((12.1,12.25),(13,13.15))]]
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def write(name,rs):
 if not rs:return
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
items=[]
for r in read(ROOT/'results/20261117/05_xrd_image_time_matching/measurement_photo_timing.csv'):
 fam=r['family'];owner=r['owner'];i=int(r['film_number']);age=r['nominal_xrd_label'];ageh=float(age[:-1]) if age.endswith('h') else np.nan
 items.append({'film':r['sample_id'],'batch':'20261117','xrd':r['txt'],'image':r['first_photo_after_xrd'],'gap_min':float(r['first_photo_after_xrd_gap_minutes']),'age_h':ageh,'sn':.1 if fam=='Sn10' else 0.,'rb':float(fam=='RbBr'),'FA':.85,'anneal_C':130.,'anneal_min':10. if owner=='Touma' else 5.,'volume':90. if owner=='Tuji' and fam=='plain' and i<=2 else 50.,'pair_note':'corrected XRD end to first subsequent photograph'})
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112'
for m in [5,10,15]:
 for age,h in [('1h',1.),('1day',24.)]:
  items.append({'film':f'20261112_Sn10_{m}min','batch':'20261112','xrd':str(next((B/'XRD'/f'{m}min'/age).glob('*.txt')).relative_to(ROOT)),'image':str(next((B/f'{m}min'/age).glob('*.jpg')).relative_to(ROOT)),'gap_min':None,'age_h':h,'sn':.1,'rb':0.,'FA':.9,'anneal_C':130.,'anneal_min':float(m),'volume':50.,'pair_note':'same nominal age only; past clock offset validity unconfirmed'})
for r in read(ROOT/'results/20261015/06_xrd_image_practice/paired_training_example.csv'):
 image=next(p for p in (ROOT/'data/raw').rglob(Path(r['image_file']).name) if ('FACsPbI3_BrRb' in str(p) if r['composition_group']=='BrRb' else '/10_15/' in str(p) and 'Sn25' in str(p)))
 items.append({'film':'20261015_'+r['sample'],'batch':'20261015','xrd':r['xrd_file'],'image':str(image.relative_to(ROOT)),'gap_min':None,'age_h':0.,'sn':0. if r['composition_group']=='BrRb' else .25,'rb':float(r['composition_group']=='BrRb'),'FA':np.nan,'anneal_C':np.nan,'anneal_min':np.nan,'volume':50.,'pair_note':'user-confirmed same film nominal0h; actual measurement gap unknown'})
ref=np.array(Image.open(ROOT/next(r['image'] for r in items if r['batch']=='20261112')).convert('RGB'))
def paper(a):return np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],axis=0)
refbg=paper(ref);rows=[];feature_rows=[];manifest=[];tiles=[]
for n,item in enumerate(items):
 x,y=np.loadtxt(ROOT/item['xrd'],skiprows=2,encoding='utf-8-sig').T;main=features(x,y,WINDOWS['main']);vals=[]
 for w in LOW:
  lo=features(x,y,w)
  if lo['resolved_by_window_rule'] and main['resolved_by_window_rule']:vals.append(lo['net_area_cps_deg']/main['net_area_cps_deg'])
 row={**item,'resolved_variants':len(vals),'target_ratio_median':float(np.median(vals)) if len(vals)>=2 else None,'target_ratio_min':min(vals) if vals else None,'target_ratio_max':max(vals) if vals else None,'target_status':'usable_candidate' if len(vals)>=2 else 'unresolved_or_unstable_not_zero'};rows.append(row)
 a=np.array(Image.open(ROOT/item['image']).convert('RGB'));quad,_=corners_and_bbox(a);poly=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(poly,quad.astype(np.int32),1)
 for xx,yy in FIT:assert not poly[yy-20:yy+20,xx-20:xx+20].any()
 crop=cv2.warpPerspective(a,cv2.getPerspectiveTransform(quad,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float);gain=refbg/paper(a)
 tiles.append((item['film']+' '+str(item['age_h']),Image.fromarray(np.uint8(crop))))
 for corrected in [False,True]:
  rgb=crop*gain if corrected else crop;gray=rgb@np.array([.2126,.7152,.0722]);smooth=cv2.GaussianBlur(gray,(0,0),8);c=(gray-smooth)/np.maximum(smooth,1);_,labels,stats,_=cv2.connectedComponentsWithStats((c>.1).astype(np.uint8),8);spots=np.isin(labels,np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1)
  for margin in [0.,.18]:
   edge=round(256*margin);mask=np.zeros((256,256),bool);mask[edge:256-edge,edge:256-edge]=True;pix=rgb[mask];g=gray[mask];fine=cv2.GaussianBlur(gray,(0,0),.7)-cv2.GaussianBlur(gray,(0,0),3)
   feature_rows.append({'row_id':n,'corrected':corrected,'margin':margin,'mean_R':pix[:,0].mean(),'mean_G':pix[:,1].mean(),'mean_B':pix[:,2].mean(),'gray_cv':g.std()/g.mean(),'spot_pct':100*spots[mask].mean(),'fine':fine[mask].std()/g.mean()})
 for key in ['image','xrd']:
  p=ROOT/item[key];manifest.append({'path':item[key],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
write('all_candidates.csv',rows);write('image_features.csv',feature_rows);(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
canvas=Image.new('RGB',(6*180,((len(tiles)+5)//6)*205),'white');draw=ImageDraw.Draw(canvas)
for i,(label,im) in enumerate(tiles):
 im=im.resize((170,170));xx=(i%6)*180;yy=(i//6)*205;canvas.paste(im,(xx,yy));draw.text((xx,yy+171),label,fill='black')
canvas.save(O/'01_crop_quality_review.jpg')
COND=['sn','rb','FA','anneal_C','anneal_min','volume','age_h'];IMG=['mean_R','mean_G','mean_B','gray_cv','spot_pct','fine'];predictions=[];scores=[]
def run(condition,ids,corr,margin,split='leave_one_film_out'):
 if len(ids)<6 or len(set(rows[i]['film'] for i in ids))<4:return
 fdict={r['row_id']:r for r in feature_rows if r['corrected']==corr and r['margin']==margin};groups=np.array([rows[i]['film'] for i in ids]);y=np.array([rows[i]['target_ratio_median'] for i in ids]);cond=np.array([[rows[i][k] for k in COND] for i in ids]);im=np.array([[fdict[i][k] for k in IMG] for i in ids]);batch=np.array([rows[i]['batch'] for i in ids]);xs={'conditions':cond,'image':im,'conditions_plus_image':np.column_stack([cond,im])}
 folds=[(groups!=g,groups==g,g) for g in sorted(set(groups))] if split=='leave_one_film_out' else [(batch!='20261117',batch=='20261117','heldout_today')]
 for train,test,fold in folds:
  if train.sum()<3 or test.sum()<1:continue
  assert not set(groups[train])&set(groups[test])
  count={g:sum(groups[train]==g) for g in set(groups[train])};weights=np.array([1/count[g] for g in groups[train]])
  baseline=float(np.average(y[train],weights=weights));yp={'training_mean':np.repeat(baseline,test.sum())}
  for name,X in xs.items():
   model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler(),Ridge(alpha=10.));model.fit(X[train],y[train],ridge__sample_weight=weights);yp[name]=model.predict(X[test])
  for name,pred in yp.items():
   for loc,val in zip(np.flatnonzero(test),pred):predictions.append({'analysis':condition,'split':split,'corrected':corr,'margin':margin,'model':name,'row_id':ids[loc],'film':groups[loc],'batch':batch[loc],'observed':y[loc],'predicted':float(val),'absolute_error':abs(float(val)-y[loc])})
 for model in ['training_mean','conditions','image','conditions_plus_image']:
  rs=[r for r in predictions if r['analysis']==condition and r['split']==split and r['corrected']==corr and r['margin']==margin and r['model']==model]
  if not rs:continue
  films=sorted(set(r['film'] for r in rs));mae=np.mean([np.mean([r['absolute_error'] for r in rs if r['film']==g]) for g in films]);rmse=np.sqrt(np.mean([np.mean([(r['predicted']-r['observed'])**2 for r in rs if r['film']==g]) for g in films]));scores.append({'analysis':condition,'split':split,'corrected':corr,'margin':margin,'model':model,'observations':len(rs),'independent_test_films':len(films),'film_weighted_MAE':mae,'film_weighted_RMSE':rmse})
sets={'today_gap_le30':[i for i,r in enumerate(rows) if r['target_status']=='usable_candidate' and r['batch']=='20261117' and r['gap_min']<=30],'today_all_gaps':[i for i,r in enumerate(rows) if r['target_status']=='usable_candidate' and r['batch']=='20261117'],'all_batches_exploratory':[i for i,r in enumerate(rows) if r['target_status']=='usable_candidate']}
for name,ids in sets.items():
 for corr in [False,True]:
  for margin in [0.,.18]:run(name,ids,corr,margin)
run('all_batches_exploratory',sets['all_batches_exploratory'],True,0.,split='older_to_today')
write('out_of_film_predictions.csv',predictions);write('validation_scores.csv',scores)
summary={'candidate_observations':len(rows),'candidate_films':len(set(r['film'] for r in rows)),'data_sets':{k:{'observations':len(ids),'films':len(set(rows[i]['film'] for i in ids))} for k,ids in sets.items()},'unresolved_not_used':sum(r['target_status']!='usable_candidate' for r in rows),'scores_primary_display':[r for r in scores if r['corrected'] and r['margin']==0.]}
(O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'target':'Median of valid12.25–13.0deg/main13.4–14.7deg net area ratios, at least2/3 backgrounds resolved; relative signal, notphasefraction','low_windows':LOW,'main_window':WINDOWS['main'],'pairing':'Today first photo after corrected XRD end; primary screening gap<=30min is provisional operational choice, not validated stability threshold; all gaps sensitivity. Older nominal pairs unknown actual gap.','model':'Ridge alpha10 fixed, no tuning or feature selection on test; training-only imputation/scaling; no negative prediction clipping','features_conditions':COND,'features_image':IMG,'evaluation':'Leaveonefilmout; all samefilm times together; equalfilm weights for fitting and MAE; older-to-today sensitivity if enough training','image_settings':'raw/corrected, margin0/.18; no ellipse exclusion;256warp; spotGaussian8 threshold10% area>=3px','warning':'Composition-dependent12.7degree candidate, not confirmed identical phase acrossfamilies. Resolved-only selection bias. No phase fraction or quality/degradation model.','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
