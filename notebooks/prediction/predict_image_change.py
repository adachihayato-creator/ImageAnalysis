"""Forecast next-observation RGB using past images only, grouped film/date validation."""
from pathlib import Path
from datetime import datetime,timedelta
import sys,json,csv,hashlib
import numpy as np,cv2
from PIL import Image
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
O=ROOT/'results/20261117/07_image_time_prediction';O.mkdir(parents=True,exist_ok=True)
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];series={};manifest=[]
def add(film,batch,group,p,label,nominal_h=None,bad=False):
 p=Path(p);p=p if p.is_absolute() else ROOT/p;j=p.with_suffix('.json')
 stamp=datetime.fromisoformat(json.loads(j.read_text())['captured_at']) if j.exists() else None
 series.setdefault(film,[]).append({'film':film,'batch':batch,'composition_group':group,'path':str(p.relative_to(ROOT)),'label':label,'nominal_h':nominal_h,'captured_at':stamp.isoformat() if stamp else None,'t':stamp.timestamp()/3600 if stamp else nominal_h,'known_problem_background':bad})
# All four October films; nominal times because metadata recording was not yet present.
for r in json.loads((ROOT/'results/20261015/05_image_time_series_0to24h/metadata.json').read_text()):add('20261015_'+r['sample'],'20261015',r['sample'].split('_')[0],r['raw'],str(r['hour'])+'h',r['hour'])
# Previous Sn5 films:0h/1h are absent, but2h->3h is usable.
b=ROOT/'data/raw/Touma/FACsSnPbI3(Sn25mol%)/20261110'
for m in [5,10]:
 for age,h in [('2h',2),('3h',3),('1day',24)]:add(f'20261110_Sn5_{m}min','20261110','Sn5',sorted((b/f'{m}min'/age).rglob('*.jpg'))[0],age,h)
# Previous Sn10 time series, preserving user labels and known problematic middle photos.
b=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112'
for m in [5,10,15]:
 ages=['1h','2h','3h','4h','1day'] if m!=15 else ['0h','1h','2h','3h','1day']
 for i,age in enumerate(ages):add(f'20261112_Sn10_{m}min','20261112','Sn10',next((b/f'{m}min'/age).glob('*.jpg')),age,24 if age=='1day' else float(age[:-1]),bad=i==1)
 stem={5:'205257_705981',10:'205350_731887',15:'205430_272313'}[m];add(f'20261112_Sn10_{m}min','20261112','Sn10',next((ROOT/'data/raw').rglob('photo_20261112_'+stem+'.jpg')),'5h' if m!=15 else '4h',5 if m!=15 else 4)
# Today ten independent films; initial0h confirmed by user.
for owner in ['Tuji','Touma']:
 for p in (ROOT/'data/raw'/owner).rglob('condition_metadata.json'):
  if not p.parent.name.startswith('20261117'):continue
  d=json.loads(p.read_text());group='RbBr20wt' if d.get('additive')=='RbBr' else ('Sn10' if d.get('Sn_fraction')==.1 else 'Pb')
  for r in d['samples']:
   film=r.get('sample_id',r.get('provisional_sample_id'));add(film,'20261117',group,r['image'],'0h',0)
   for v in r.get('time_series',[]):add(film,'20261117',group,v['image'],v['elapsed_age'],float(v['elapsed_age'][:-1]))
for ss in series.values():ss.sort(key=lambda v:v['t'])
assert len(series)==19
features={};obsrows=[]
for film,ss in series.items():
 first=np.array(Image.open(ROOT/ss[0]['path']).convert('RGB'))
 def paper(a):return np.mean([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in FIT],axis=0)
 ref=paper(first)
 for v in ss:
  p=ROOT/v['path'];a=np.array(Image.open(p).convert('RGB'));quad,_=corners_and_bbox(a);poly=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(poly,quad.astype(np.int32),1)
  for x,y in FIT:assert not poly[y-20:y+20,x-20:x+20].any(),p
  raw=cv2.warpPerspective(a,cv2.getPerspectiveTransform(quad,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float);gain=ref/paper(a)
  for corrected in [False,True]:
   rgb=raw*gain if corrected else raw;gray=rgb@np.array([.2126,.7152,.0722]);smooth=cv2.GaussianBlur(gray,(0,0),8);contrast=(gray-smooth)/np.maximum(smooth,1);_,labels,stats,_=cv2.connectedComponentsWithStats((contrast>.1).astype(np.uint8),8);spot=np.isin(labels,np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1);fine=cv2.GaussianBlur(gray,(0,0),.7)-cv2.GaussianBlur(gray,(0,0),3)
   for margin in [0.,.18]:
    n=round(256*margin);sl=np.s_[n:256-n,n:256-n];pix=rgb[sl];g=gray[sl];mean=pix.mean((0,1));feat=np.r_[mean,g.std()/g.mean(),spot[sl].mean()*100,fine[sl].std()/g.mean()];features[v['path'],corrected,margin]=feat
    obsrows.append({**v,'corrected':corrected,'margin':margin,'mean_R':mean[0],'mean_G':mean[1],'mean_B':mean[2],'gray_cv':feat[3],'spot_pct':feat[4],'fine':feat[5]})
  manifest.append({'path':v['path'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  if p.with_suffix('.json').exists():manifest.append({'path':str(p.with_suffix('.json').relative_to(ROOT)),'sha256':hashlib.sha256(p.with_suffix('.json').read_bytes()).hexdigest()})
def write(name,rs):
 if not rs:return
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
write('image_observations.csv',obsrows);(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
# Candidate task chosen from available timing, before fitting or scoring.
pairs=[]
for mode in ['exclude_known_bad','include_known_bad']:
 for film,ss in series.items():
  clean=[v for v in ss if mode=='include_known_bad' or not v['known_problem_background']]
  for i in range(len(clean)-1):
   cur,nxt=clean[i:i+2];h=nxt['t']-cur['t'];prev=clean[i-1] if i else None
   status='use' if .5<=h<=2. else 'outside_30to120min'
   pairs.append({'mode':mode,'film':film,'batch':cur['batch'],'composition_group':cur['composition_group'],'current_image':cur['path'],'target_image':nxt['path'],'previous_image':prev['path'] if prev else None,'current_label':cur['label'],'target_label':nxt['label'],'horizon_h':h,'previous_gap_h':cur['t']-prev['t'] if prev else None,'status':status,'time_basis':'camera timestamp' if cur['captured_at'] else 'nominal hours only'})
write('forecast_pairs.csv',pairs)
def matrices(ps,corr,margin):
 X=[];Y=[];base=[];trend=[]
 for p in ps:
  a=features[p['current_image'],corr,margin];b=features[p['target_image'],corr,margin];prev=features.get((p['previous_image'],corr,margin));gap=p['previous_gap_h'];valid=prev is not None and .25<=gap<=3
  rates=(a[:3]-prev[:3])/gap if valid else np.zeros(3)
  # No composition, sample ID, calendar date, XRD or target-paper statistics in input.
  X.append(np.r_[a,rates,float(valid),gap if valid else 0.,p['horizon_h']]);Y.append((b[:3]-a[:3])/p['horizon_h']);base.append(a[:3]);trend.append(rates)
 return np.array(X),np.array(Y),np.array(base),np.array(trend)
preds=[];scores=[]
def eval_set(ps,mode,corr,margin,split):
 X,Y,current,trend=matrices(ps,corr,margin);groups=np.array([r['film'] for r in ps]);batches=np.array([r['batch'] for r in ps]);h=np.array([r['horizon_h'] for r in ps]);folds=[]
 if split=='leave_one_film_out':folds=[(groups!=g,groups==g,g) for g in sorted(set(groups))]
 if split=='leave_one_batch_out':folds=[(batches!=b,batches==b,b) for b in sorted(set(batches))]
 if split=='older_to_today':folds=[(batches!='20261117',batches=='20261117','today')]
 for train,test,fold in folds:
  assert not set(groups[train])&set(groups[test]);count={g:sum(groups[train]==g) for g in set(groups[train])};w=np.array([1/count[g] for g in groups[train]])
  models={'ridge':make_pipeline(StandardScaler(),Ridge(alpha=10.)), 'random_forest':RandomForestRegressor(n_estimators=200,max_depth=3,min_samples_leaf=4,max_features=1.,random_state=42,n_jobs=1)}
  predicted={'persistence':np.zeros((test.sum(),3)),'linear_trend':trend[test],'training_mean_change':np.tile(np.average(Y[train],axis=0,weights=w),(test.sum(),1))}
  for name,model in models.items():
   if name=='ridge':model.fit(X[train],Y[train],ridge__sample_weight=w)
   else:model.fit(X[train],Y[train],sample_weight=w)
   predicted[name]=model.predict(X[test])
  for name,out in predicted.items():
   for pos,rate in zip(np.flatnonzero(test),out):
    actual=current[pos]+Y[pos]*h[pos];forecast=current[pos]+rate*h[pos];p=ps[pos]
    row={'mode':mode,'corrected':corr,'margin':margin,'split':split,'model':name,'film':p['film'],'batch':p['batch'],'composition_group':p['composition_group'],'current_image':p['current_image'],'target_image':p['target_image'],'horizon_h':h[pos]}
    for k,c in enumerate('RGB'):row['actual_'+c]=actual[k];row['predicted_'+c]=forecast[k];row['abs_error_'+c]=abs(forecast[k]-actual[k])
    row['MAE_RGB']=np.abs(forecast-actual).mean();preds.append(row)
 for name in ['persistence','linear_trend','training_mean_change','ridge','random_forest']:
  rs=[r for r in preds if r['mode']==mode and r['corrected']==corr and r['margin']==margin and r['split']==split and r['model']==name];films=sorted(set(r['film'] for r in rs));mae=np.mean([np.mean([r['MAE_RGB'] for r in rs if r['film']==g]) for g in films]);r={'mode':mode,'corrected':corr,'margin':margin,'split':split,'model':name,'pairs':len(rs),'independent_films':len(films),'film_weighted_MAE_RGB':mae}
  for c in 'RGB':r['MAE_'+c]=np.mean([np.mean([x['abs_error_'+c] for x in rs if x['film']==g]) for g in films])
  scores.append(r)
for mode in ['exclude_known_bad','include_known_bad']:
 ps=[p for p in pairs if p['mode']==mode and p['status']=='use']
 for corr,margin in [(False,0.),(True,0.),(False,.18),(True,.18)]:eval_set(ps,mode,corr,margin,'leave_one_film_out')
 # More demanding test: models trained on previous batches never see today's outcome labels.
 if mode=='exclude_known_bad':
  for split in ['leave_one_batch_out','older_to_today']:eval_set(ps,mode,True,0.,split)
write('heldout_predictions.csv',preds);write('validation_scores.csv',scores)
# Actual one-hour-ahead forecast for today's latest observations, fitted ONLY on older batches.
ps=[p for p in pairs if p['mode']=='exclude_known_bad' and p['status']=='use'];X,Y,_,_=matrices(ps,True,0.);older=np.array([p['batch']!='20261117' for p in ps]);g=np.array([p['film'] for p in ps]);weights=np.array([1/sum(g[older]==z) for z in g[older]]);model=make_pipeline(StandardScaler(),Ridge(alpha=10.));model.fit(X[older],Y[older],ridge__sample_weight=weights);future=[]
for film,ss in series.items():
 if ss[0]['batch']!='20261117':continue
 clean=[v for v in ss if not v['known_problem_background']];cur=clean[-1];prev=clean[-2] if len(clean)>1 else None;a=features[cur['path'],True,0.];gap=cur['t']-prev['t'] if prev else 0;valid=prev is not None and .25<=gap<=3;rates=(a[:3]-features[prev['path'],True,0.][:3])/gap if valid else np.zeros(3);feat=np.r_[a,rates,float(valid),gap if valid else 0.,1.];forecast=a[:3]+model.predict(feat.reshape(1,-1))[0];when=datetime.fromisoformat(cur['captured_at'])+timedelta(hours=1)
 row={'film':film,'composition_group':cur['composition_group'],'latest_image':cur['path'],'latest_label':cur['label'],'latest_capture_time':cur['captured_at'],'forecast_time':when.isoformat(),'horizon_h':1.,'model':'ridge_older_batches_only','background_reference':'each film initial photo; compare future after same per-channel paper normalization','status':'UNVERIFIED forecast; model reliability assessed separately'}
 for k,c in enumerate('RGB'):row['current_'+c]=a[k];row['forecast_'+c]=forecast[k];row['persistence_'+c]=a[k]
 future.append(row)
write('next_1h_forecasts_UNVERIFIED.csv',future)
summary={'films':len(series),'source_photos':sum(len(s) for s in series.values()),'primary_pairs':sum(p['mode']=='exclude_known_bad' and p['status']=='use' for p in pairs),'pair_counts_by_batch':{b:sum(p['mode']=='exclude_known_bad' and p['status']=='use' and p['batch']==b for p in pairs) for b in sorted(set(p['batch'] for p in pairs))},'primary_scores':[r for r in scores if r['mode']=='exclude_known_bad' and r['corrected'] and r['margin']==0.],'next_forecasts':len(future)}
(O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));(O/'analysis_config.json').write_text(json.dumps({'task':'Current image plus available past trend -> next observed mean RGB30–120min later','input':'meanRGB, grayCV, spotpct, finepattern, previousRGB slopes and availability/gap, next horizon. No composition, owner, date orXRD in model.','primary_target':'future meanRGB in JPEG units, modeled as hourlychange and multiplied byforecast horizon','training':'19films, leavefilmout or leavebatchout; all samefilm samples grouped; equalfilm weights; train-onlyStandardScaler; Ridge alpha10 fixed; RF200trees depth3 leaf4 fixed','correction':'Eachfilm FIRST photo paper as its own reference; prediction input uses only past/current paper. Future paper is used ONLY to define measured corrected target. Future paper normalization must be available when evaluating. Not a forecast of future lighting.','image_method':'quadrilateral warp256, fullframe primary; raw andmargin18% sensitivity; ellipse included. No physical colorcalibration.','known_bad':'Nov12 secondphotos only excluded inprimary; includeall sensitivity. October nominaltime uncertainty andBrRb1alignment remain.','forecast_output':'Next1h currentfilms forecast using older batches only; no future observed labels, UNVERIFIED.','long_horizon':'24h images retained ininventory but not scored as1h forecast because horizon outside30–120min','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
