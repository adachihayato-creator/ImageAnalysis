"""Extend the frozen descriptive image/XRD methods to nominal one-day data."""
from pathlib import Path
import sys,json,csv,hashlib
import numpy as np,cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
from analyze_sn10_xrd import features,scan_metadata,WINDOWS
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox
B=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112'
O=ROOT/'results/20261113/08_1day_image_xrd';O.mkdir(parents=True,exist_ok=True)
(O/'crops').mkdir(exist_ok=True)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':11})
FIT=[(785,555),(1585,555),(1185,250),(1185,855)];CHECK=[(785,250),(1585,250),(785,855),(1585,855)]
LOW=[{'search':(12.25,13),'background':b} for b in [((11.5,11.8),(13.1,13.3)),((12,12.2),(13.05,13.2)),((12.1,12.25),(13,13.15))]]
manifest=[]
def rec(p):manifest.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
def write(n,rows):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save(fig,n):fig.savefig(O/(n+'.png'),dpi=160,bbox_inches='tight');plt.close(fig)
def patches(a,centers):return np.array([a[y-20:y+20,x-20:x+20].mean((0,1)) for x,y in centers])
def photo(m,age):
 if age in ['5h','4h']:
  stem={5:'205257_705981',10:'205350_731887',15:'205430_272313'}[m]
  return next((ROOT/'data/raw').rglob('photo_20261112_'+stem+'.jpg'))
 return next((B/f'{m}min'/age).glob('*.jpg'))
ref=np.array(Image.open(photo(5,'1h')).convert('RGB')); refbg=patches(ref,FIT).mean(0);refcheck=patches(ref,CHECK)
xrows=[];sens=[];scans={}
for m in [5,10,15]:
 for age in ['0h','1h','5h','1day']:
  folder=B/'XRD'/f'{m}min'/age;p=next(folder.glob('*.txt'));z=next(folder.glob('*.rasx'));x,y=np.loadtxt(p,skiprows=2,encoding='utf-8-sig').T;meta,native=scan_metadata(z);dt=float(meta['Step'])/(float(meta['Speed'])/60)
  assert len(x)==5701 and np.allclose(x,native[:,0]) and np.allclose(y,native[:,1]/dt,rtol=1e-6,atol=.001)
  row={'anneal_min':m,'age':age}
  for k in ['main','high']:row.update({k+'_'+q:v for q,v in features(x,y,WINDOWS[k]).items()})
  vals=[]
  for j,w in enumerate(LOW):
   f=features(x,y,w);r=f['net_area_cps_deg']/row['main_net_area_cps_deg'] if f['resolved_by_window_rule'] and row['main_resolved_by_window_rule'] else None
   sens.append({'anneal_min':m,'age':age,'background_variant':j+1,'ratio':r,**f})
   if r is not None:vals.append(r)
  row.update({'ratio_min':min(vals) if vals else None,'ratio_max':max(vals) if vals else None,'resolved_variants':len(vals)})
  xrows.append(row);scans[m,age]=(x,y);rec(p);rec(z)
write('xrd_features.csv',xrows);write('xrd_low_peak_sensitivity.csv',sens)
rows=[];validation=[];crops={};spotmaps={};mesh=[];cornerrows=[]
for m in [5,10,15]:
 ages=['1h','2h','3h','4h','5h','1day'] if m!=15 else ['0h','1h','2h','3h','4h','1day']
 for age in ages:
  p=photo(m,age);a=np.array(Image.open(p).convert('RGB'));meta=json.loads(p.with_suffix('.json').read_text());quad,_=corners_and_bbox(a);poly=np.zeros(a.shape[:2],np.uint8);cv2.fillConvexPoly(poly,quad.astype(np.int32),1)
  for x,y in FIT+CHECK:assert not poly[y-20:y+20,x-20:x+20].any(),(m,age,'background overlaps film')
  raw=cv2.warpPerspective(a,cv2.getPerspectiveTransform(quad,np.float32([[0,0],[255,0],[255,255],[0,255]])),(256,256)).astype(float);bg=patches(a,FIT).mean(0);gain=refbg/bg;check=patches(a,CHECK)
  err=lambda c:float(100*np.mean(np.sqrt(np.mean(((c-refcheck)/refcheck)**2,axis=1))))
  validation.append({'anneal_min':m,'age':age,'filename':p.name,'captured_at':meta['captured_at'],'fixed_settings_verified':meta.get('fixed_settings_verified'),'background_R':bg[0],'background_G':bg[1],'background_B':bg[2],'heldout_error_before_pct':err(check),'heldout_error_after_pct':err(check*gain)})
  cornerrows.append({'anneal_min':m,'age':age,'corners':quad.tolist(),'filename':p.name})
  rec(p);rec(p.with_suffix('.json'))
  for corrected in [False,True]:
   rgb=raw*gain if corrected else raw;gray=rgb@np.array([.2126,.7152,.0722]);smooth=cv2.GaussianBlur(gray,(0,0),8);contrast=(gray-smooth)/np.maximum(smooth,1);n,labels,stats,_=cv2.connectedComponentsWithStats((contrast>.1).astype('uint8'),8);valid=np.flatnonzero(stats[1:,cv2.CC_STAT_AREA]>=3)+1;spots=np.isin(labels,valid)
   for margin in [0,.05,.18]:
    edge=round(256*margin);mask=np.zeros((256,256),bool);mask[edge:256-edge,edge:256-edge]=True;pix=rgb[mask];g=gray[mask];fine=cv2.GaussianBlur(gray,(0,0),.7)-cv2.GaussianBlur(gray,(0,0),3)
    rows.append({'anneal_min':m,'age':age,'corrected':corrected,'margin':margin,'mean_R':pix[:,0].mean(),'mean_G':pix[:,1].mean(),'mean_B':pix[:,2].mean(),'bright_area_percent':100*spots[mask].mean(),'fine_pattern_sd_over_mean':fine[mask].std()/g.mean(),'gray_cv':g.std()/g.mean()})
   if corrected:
    crops[m,age]=np.uint8(np.clip(np.rint(rgb),0,255));spotmaps[m,age]=spots
    if age in ['1h','1day']:Image.fromarray(crops[m,age]).save(O/'crops'/f'{m}min_{age}_corrected.png')
    for iy in range(8):
     for ix in range(8):
      sl=np.s_[iy*32:(iy+1)*32,ix*32:(ix+1)*32];v=rgb[sl].mean((0,1));mesh.append({'anneal_min':m,'age':age,'row':iy+1,'column':ix+1,'bright_area_percent':100*spots[sl].mean(),'mean_R':v[0],'mean_G':v[1],'mean_B':v[2]})
write('image_features.csv',rows);write('heldout_background.csv',validation);write('mesh_8x8.csv',mesh)
(O/'detected_corners.json').write_text(json.dumps(cornerrows,indent=2))
primary=lambda m,age:next(r for r in rows if r['anneal_min']==m and r['age']==age and r['corrected'] and r['margin']==0)
paired=[]
for m in [5,10,15]:
 for age in ['1h','1day']:
  im=primary(m,age);xr=next(r for r in xrows if r['anneal_min']==m and r['age']==age);paired.append({**im,'xrd_ratio_min':xr['ratio_min'],'xrd_ratio_max':xr['ratio_max'],'xrd_resolved_variants':xr['resolved_variants']})
write('paired_1h_1day.csv',paired)
config={'independent_films':3,'per_condition_films':1,'age':'User nominal labels; 1day is not exact 24h. XRD clock ignored. Photo/XRD not assumed simultaneous.','background_reference':str(photo(5,'1h').relative_to(ROOT)),'fit':FIT,'heldout':CHECK,'patch_size_px':40,'warp_size':[256,256],'primary_image':'full substrate quadrilateral, no ellipse exclusion, no edge exclusion','spot':'contrast (gray-Gaussian_sigma8)/max(Gaussian_sigma8,1)>0.10, component>=3px; segmented once on full frame then region partition','margins':[0,.05,.18],'low_peak_windows':LOW,'main_windows':WINDOWS,'image_second_points':'5/10min2h and15min1h problematic backgrounds; shown distinctly, not used to infer clean time trends','not_phase_fraction':True,'not_physical_degradation_proof':True,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(O/'analysis_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2));(O/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
# 1: matched one-hour/day observations with identical display scale.
fig,axes=plt.subplots(3,4,figsize=(12,10))
for i,m in enumerate([5,10,15]):
 for j,age in enumerate(['1h','1day']):
  rgb=crops[m,age];overlay=rgb.copy();overlay[spotmaps[m,age]]=[255,220,0]
  axes[i,2*j].imshow(rgb);axes[i,2*j+1].imshow(overlay)
  axes[i,2*j].set_title(f'{m}分膜・{age} 補正後');axes[i,2*j+1].set_title(f'斑点候補 {primary(m,age)["bright_area_percent"]:.2f}%')
 for ax in axes[i]:ax.axis('off')
fig.suptitle('1hと1日後：全体領域／黄は局所的に明るい領域、化学相の同定ではない');fig.tight_layout();save(fig,'01_1hと1日後の画像と斑点')
# 2: full chronological record with suspect images marked.
fig,axes=plt.subplots(3,3,figsize=(14,10))
for i,m in enumerate([5,10,15]):
 vr=[v for v in validation if v['anneal_min']==m];ages=[v['age'] for v in vr]
 for j,key in enumerate(['mean_R','mean_G','mean_B']):
  ax=axes[i,j]
  for corr,style in [(False,'--'),(True,'-')]:
   vals=[next(r[key] for r in rows if r['anneal_min']==m and r['age']==a and r['corrected']==corr and r['margin']==0) for a in ages];vals=np.array(vals)-vals[0];ax.plot(range(len(ages)),vals,style+'o',label='背景補正あり' if corr else '補正なし')
  ax.axvspan(.75,1.25,color='orange',alpha=.15);ax.axhline(0,color='gray',lw=.5);ax.set_xticks(range(len(ages)),ages);ax.set_title(f'{m}分膜：{key[-1]} 初回との差');ax.grid(alpha=.2)
axes[0,0].legend();fig.suptitle('全体平均RGB：横軸は公称時点を等間隔表示／橙は背景差が大きい既知の画像');fig.tight_layout();save(fig,'02_RGB経時変化_補正ありなし')
fig,axes=plt.subplots(3,2,figsize=(12,10))
for i,m in enumerate([5,10,15]):
 for age,col in zip(['0h','1h','5h','1day'],['gray','#287bab','#dc8a26','#994499']):
  x,y=scans[m,age];s=np.convolve(y,np.ones(5)/5,'same');norm=s[(x>=13.4)&(x<=14.7)].max();axes[i,0].plot(x,s/norm,label=age,color=col)
 axes[i,0].set_xlim(11.5,15.2);axes[i,0].set_title(f'{m}分膜：約14°最大値で規格化（背景込み）');axes[i,0].set_xlabel('2θ (°)');axes[i,0].legend();axes[i,0].grid(alpha=.2)
 for j,a in enumerate(['0h','1h','5h','1day']):
  r=next(r for r in xrows if r['anneal_min']==m and r['age']==a)
  if r['ratio_min'] is not None:axes[i,1].plot([j,j],[r['ratio_min'],r['ratio_max']],lw=7,color='#287bab');axes[i,1].plot(j,(r['ratio_min']+r['ratio_max'])/2,'ko',ms=3)
  else:axes[i,1].text(j,.015,'抽出不成立',rotation=90,ha='center',fontsize=9)
 axes[i,1].set_xticks(range(4),['0h','1h','5h','1day']);axes[i,1].set_ylim(bottom=0);axes[i,1].set_ylabel('副相候補／主ピークの面積比');axes[i,1].set_title('3通りの背景処理の範囲（信頼区間ではない）');axes[i,1].grid(alpha=.2)
fig.tight_layout();save(fig,'03_XRD_1日後まで')
fig,axes=plt.subplots(2,3,figsize=(13,8))
for j,m in enumerate([5,10,15]):
 for region,col in [(0,'#287bab'),(.05,'#dc8a26'),(.18,'#27955f')]:
  ages=[v['age'] for v in validation if v['anneal_min']==m];vals=[next(r['bright_area_percent'] for r in rows if r['anneal_min']==m and r['age']==a and r['corrected'] and r['margin']==region) for a in ages];axes[0,j].plot(range(len(ages)),vals,'o-',label={0:'全体',.05:'外周5%除外',.18:'外周18%除外'}[region])
 axes[0,j].set_xticks(range(len(ages)),ages);axes[0,j].set_title(f'{m}分膜：斑点候補面積率 (%)');axes[0,j].grid(alpha=.2);axes[0,j].legend(fontsize=8)
 d=np.zeros((8,8))
 for rr in range(8):
  for cc in range(8):
   val=lambda a:next(r['bright_area_percent'] for r in mesh if r['anneal_min']==m and r['age']==a and r['row']==rr+1 and r['column']==cc+1)
   d[rr,cc]=val('1day')-val('1h')
 im=axes[1,j].imshow(d,cmap='coolwarm',vmin=-30,vmax=30);axes[1,j].set_title(f'{m}分膜：1day−1h（ポイント）');axes[1,j].set_xticks(range(8),range(1,9));axes[1,j].set_yticks(range(8),range(1,9));fig.colorbar(im,ax=axes[1,j],shrink=.75)
fig.suptitle('区画変化は位置合わせの残差を含む／64区画は独立した64膜ではない');fig.tight_layout();save(fig,'04_斑点の経時変化と8x8分布')
print(json.dumps({'paired':paired,'latest_background':[v for v in validation if v['age']=='1day'],'xrd':xrows},ensure_ascii=False,default=float,indent=2))
fig,axes=plt.subplots(1,2,figsize=(11,4.8))
for m,col in zip([5,10,15],['gray','#287bab','#dc8a26']):
 pts=[r for r in paired if r['anneal_min']==m]
 axes[0].plot([0,1],[r['bright_area_percent'] for r in pts],'o-',label=f'{m}分',color=col)
 for i,r in enumerate(pts):
  if r['xrd_ratio_min'] is not None:axes[1].plot([i,i],[r['xrd_ratio_min'],r['xrd_ratio_max']],lw=6,color=col)
 if all(r['xrd_ratio_min'] is not None for r in pts):axes[1].plot([0,1],[(r['xrd_ratio_min']+r['xrd_ratio_max'])/2 for r in pts],'o--',color=col,label=f'{m}分')
for ax in axes:ax.set_xticks([0,1],['1h','1日後']);ax.grid(alpha=.2);ax.legend()
axes[0].set_ylabel('斑点候補の面積率 (%)');axes[0].set_title('画像：全体・背景補正後');axes[1].set_ylabel('副相候補／主ピークの面積比');axes[1].set_title('XRD：棒は背景処理の範囲\n5分膜は両時点とも抽出不成立')
fig.suptitle('15分膜は両指標が減少／10分膜の画像指標はほぼ横ばい');fig.tight_layout();save(fig,'05_画像とXRDの時間変化の対応')
lines=['# 1日後までの画像・XRD解析','', '既存の方法を変えず、3膜の1日後を追加。XRDは0h/1h/5h/1dayの12測定、画像は各膜6時点の18枚。1dayはユーザー指定の公称ラベル。XRD装置時計は比較に使用していません。','', '## 結果：1h → 1日後','', '| 膜 | 斑点候補面積率（全体・補正後） | 副相候補／主ピーク面積比 |','|---|---|---|']
for m in [5,10,15]:
 a,b=[r for r in paired if r['anneal_min']==m]
 ratio=lambda r: f"{r['xrd_ratio_min']:.3f}–{r['xrd_ratio_max']:.3f}" if r['xrd_ratio_min'] is not None else '抽出不成立（ゼロではない）'
 lines.append(f"| {m}分 | {a['bright_area_percent']:.2f}% → {b['bright_area_percent']:.2f}% | {ratio(a)} → {ratio(b)} |")
lines+=['','15分膜では斑点候補面積率が約2.83ポイント低下し、XRDの相対面積比も低下しました。画像の減少は補正あり／なし、外周除外0／5／18%の6条件で共通しています。単に外周を含めた場合だけに現れる結果ではありません。ただし、反射・ピント・画角位置等を完全に分離したものではありません。','', '10分膜はXRDの相対面積比が下がりましたが、全体の斑点面積率はほぼ横ばいでした。外周5%・18%除外では小幅増加となるため、画像の小さな増減の方向は領域依存です。1日後の副相候補抽出は3種類の背景のうち2種類でのみ成立する弱い信号であり、精密な減少率は示しません。','', '5分膜は斑点面積率がほぼ横ばい。XRDの副相候補は1hも1日後も抽出不成立であり、「存在しない」「ゼロ」とは言えません。','', '1日後も15分膜は3膜中で斑点面積率とXRD相対面積比がともに最大です。ただし、1h時点の斑点面積率の差は縮小しました。膜同士の順位の対応は残っていますが、全膜の時間変化を斑点だけで説明する共通の関係は確認できません。','', '## RGBと区画解析','', '全体・共通背景基準で補正後の1day−1h（JPEG RGB単位）：']
for m in [5,10,15]:
 a=primary(m,'1h');b=primary(m,'1day');lines.append(f"- {m}分：R {b['mean_R']-a['mean_R']:+.2f}、G {b['mean_G']-a['mean_G']:+.2f}、B {b['mean_B']-a['mean_B']:+.2f}。")
lines+=['','RGBの変化をそのまま黄色化、PbI₂量、性能低下とは解釈しません。15分膜の1h画像は既知の背景差が大きい写真なので、色の経時変化は特に慎重に解釈します。斑点減少については補正なしでも同方向で、問題の1h画像を外して公称3h・4hから1日後を比べた数値もCSVで確認できます。','', '8×8の64区画に分け、斑点面積率の1day−1hを図04下段に表示しました。これは局所変化の可視化であり、64枚の独立試料を意味しません。四角形への変換のみで内部の厳密な画素位置合わせは行っていないため、個々の区画の増減は位置合わせ残差も含みます。','', '## XRDの解釈上の限界','', '面積比は約12.7°候補ピークを約14°主ピークで割った相対指標です。低下はPbI₂の絶対量低下や相含有率低下を証明しません。主ピーク強度・配向・測定位置・背景の影響を含みます。主ピークの見かけ半値幅は1h→1dayで5分0.466→0.340°、10分0.341→0.394°、15分0.363→0.308°と膜ごとに異なります。装置幅補正なしなので結晶性や結晶粒径の断定には使いません。','', '各条件1膜、独立膜数3。統計的な相関の立証、予測モデル、斑点の化学相同定、良膜判定は行っていません。','', '## 確認と図の見方','', 'TXTとRASXの角度・カウントからcpsへの換算一致を12測定すべてで確認。全画像で背景測定領域が検出した基板四角形と重ならないことを確認。最新3画像の保存設定照合はすべて成功。補正に未使用の背景での相対RGBずれは5分7.18→1.45%、10分5.47→0.79%、15分7.63→1.65%。これは膜の色の正確さを保証する値ではありません。','', '- まず図05：画像とXRDの1h→1日後の変化を左右で比較。XRDの棒は背景処理3条件の範囲で、信頼区間ではありません。','- 図01：補正画像と黄色の斑点候補を目で確認。','- 図03：XRD全時点と相対面積比。抽出不成立をゼロとして結ばない。','- 図04：全体／外周除外の比較と8×8分布。','- 図02：RGBの全時点。橙の時点は既知の背景差が大きい画像で、傾向の断定には使わない。','', '再実行：`PYTHONPATH=/tmp/film-analysis-deps MPLCONFIGDIR=/tmp/film-mpl python3 notebooks/film_time_series/analyze_sn10_1day.py`。入力ハッシュはinput_manifest.json、方法はanalysis_config.json、数値は各CSV。既存の解析は上書きしていません。']
lines += ['', '追加確認：15分膜の全体斑点面積率（補正後）は成膜直後15.38%、1h18.28%、2h17.41%、3h17.18%、公称4h17.11%、1日後15.45%。初期から単調増加しておらず、1日後は初期に近い値です。背景差が大きい1hを外しても3h・4hから1日後に減少します。ただし原因を材料変化と断定できません。']
(O/'README.md').write_text('\n'.join(lines)+'\n')
