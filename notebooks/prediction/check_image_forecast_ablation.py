from pathlib import Path
import csv,numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'results/20261117/07_image_time_prediction'
def read(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
features={r['path']:np.array([float(r[k]) for k in ['mean_R','mean_G','mean_B','gray_cv','spot_pct','fine']]) for r in read('image_observations.csv') if r['corrected']=='True' and float(r['margin'])==0}
ps=[p for p in read('forecast_pairs.csv') if p['mode']=='exclude_known_bad' and p['status']=='use'];X=[];Y=[];H=[]
for p in ps:
 a=features[p['current_image']];b=features[p['target_image']];h=float(p['horizon_h']);gap=float(p['previous_gap_h']) if p['previous_gap_h'] else 0;valid=bool(p['previous_image']) and .25<=gap<=3;rates=(a[:3]-features[p['previous_image']][:3])/gap if valid else np.zeros(3);X.append(np.r_[a,rates,float(valid),gap if valid else 0.,h]);Y.append((b[:3]-a[:3])/h);H.append(h)
X=np.array(X);Y=np.array(Y);H=np.array(H);groups=np.array([p['film'] for p in ps]);batches=np.array([p['batch'] for p in ps]);out=[]
for split in ['leave_one_film_out','older_to_today']:
 folds=[(groups!=g,groups==g) for g in sorted(set(groups))] if split=='leave_one_film_out' else [(batches!='20261117',batches=='20261117')]
 for name,columns in [('history_only',list(range(6,12))),('meanRGB_plus_history',[0,1,2]+list(range(6,12))),('all_image_plus_history',list(range(12)))]:
  values=[]
  for train,test in folds:
   w=np.array([1/sum(groups[train]==g) for g in groups[train]]);model=make_pipeline(StandardScaler(),Ridge(alpha=10.));model.fit(X[train][:,columns],Y[train],ridge__sample_weight=w);pred=model.predict(X[test][:,columns]);err=np.abs((pred-Y[test])*H[test,None]).mean(1)
   values.extend(zip(groups[test],err))
  mae=np.mean([np.mean([v for g,v in values if g==film]) for film in sorted(set(g for g,v in values))]);out.append({'split':split,'model':name,'film_weighted_MAE_RGB':mae,'observations':len(values),'films':len(set(g for g,v in values))})
with (O/'image_feature_ablation.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
for r in out:print(r)
