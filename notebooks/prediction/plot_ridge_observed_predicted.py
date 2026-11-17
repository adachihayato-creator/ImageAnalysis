"""Observed versus genuinely held-out Ridge forecasts; show levels and changes separately."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'results/20261117/07_image_time_prediction'
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':12})
def read(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
allpred=read('heldout_predictions.csv');obs={r['path']:r for r in read('image_observations.csv') if r['corrected']=='True' and float(r['margin'])==0}
score=read('validation_scores.csv');batches=['20261015','20261110','20261112','20261117'];colors=['#777777','#9b59b6','#dc8a26','#287bab'];export=[];r2_rows=[]
for split,prefix,title in [('leave_one_film_out','05','膜単位で評価：19膜・64組'),('older_to_today','07','過去9膜で学習→今日10膜を予測：36組')]:
 rs=[r for r in allpred if r['mode']=='exclude_known_bad' and r['corrected']=='True' and float(r['margin'])==0 and r['split']==split and r['model']=='ridge'];assert len(rs)==(64 if split=='leave_one_film_out' else 36)
 for delta in [False,True]:
  fig,axes=plt.subplots(1,3,figsize=(14,6.0))
  for ax,c in zip(axes,'RGB'):
   x=np.array([float(r['actual_'+c]) for r in rs]);y=np.array([float(r['predicted_'+c]) for r in rs]);current=np.array([float(obs[r['current_image']]['mean_'+c]) for r in rs])
   if delta:x=x-current;y=y-current
   residual=float(np.sum((y-x)**2));total=float(np.sum((x-x.mean())**2));r2=1-residual/total if total>0 else np.nan
   weights=np.array([1/sum(v['film']==r['film'] for v in rs) for r in rs]);mu=np.average(x,weights=weights);den=np.sum(weights*(x-mu)**2);weighted_r2=1-np.sum(weights*(y-x)**2)/den if den>0 else np.nan
   r2_rows.append({'split':split,'quantity':'change' if delta else 'level','channel':c,'pairs':len(rs),'films':len(set(r['film'] for r in rs)),'R2_all_points':float(r2),'R2_equal_film_weights':float(weighted_r2),'definition':'1-SSE/SST; not squared Pearson correlation; predictions unchanged'})
   values=np.r_[x,y];lo=min(values.min(),0) if delta else values.min();hi=max(values.max(),0) if delta else values.max();pad=max((hi-lo)*.1,.5);lo-=pad;hi+=pad
   for batch,col in zip(batches,colors):
    mask=np.array([r['batch']==batch for r in rs])
    if mask.any():ax.scatter(x[mask],y[mask],s=35,color=col,label=batch,alpha=.8,edgecolor='white',lw=.4)
   ax.plot([lo,hi],[lo,hi],'k--',lw=1.2,label='予測＝実測');ax.set_xlim(lo,hi);ax.set_ylim(lo,hi);ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.2)
   if delta:ax.axhline(0,color='gray',lw=.6);ax.axvline(0,color='gray',lw=.6)
   mae=float(next(r['MAE_'+c] for r in score if r['mode']=='exclude_known_bad' and r['corrected']=='True' and float(r['margin'])==0 and r['split']==split and r['model']=='ridge'));ax.set_title(f'{c}：R² = {r2:.3f}\n平均絶対誤差 {mae:.2f}');ax.set_xlabel('実測の変化量' if delta else '実測の平均RGB');ax.set_ylabel('予測の変化量' if delta else '予測の平均RGB')
   for r,xx,yy in zip(rs,x,y):export.append({'split':split,'quantity':'change' if delta else 'level','channel':c,'film':r['film'],'current_image':r['current_image'],'target_image':r['target_image'],'observed':xx,'predicted':yy})
  axes[0].legend(fontsize=8,loc='best');kind='変化量（次の値−現在値）' if delta else '次の撮影時点の平均RGB'
  fig.suptitle(f'Ridge回帰：{kind}\n{title}／背景補正後・全体領域',fontsize=15)
  note='点は予測区間。R²は全点の1−SSE/SST（膜別等重み版はCSV）。MAEは膜別等重み。破線は予測＝実測。'
  if not delta:note+='\n値の図だけでは「変化しない」予測も良く見えるため変化量図も確認。'
  fig.text(.5,.012,note,ha='center',fontsize=9);fig.tight_layout(rect=[0,.14,1,.87])
  num='06' if prefix=='05' and delta else ('08' if prefix=='07' and delta else prefix);name=num+'_Ridge_実測と予測_'+('変化量' if delta else 'RGB値')
  fig.savefig(O/(name+'.png'),dpi=160,bbox_inches='tight');plt.close(fig)
with (O/'ridge_scatter_points.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(export)
with (O/'ridge_R2.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(r2_rows[0]));w.writeheader();w.writerows(r2_rows)
p=O/'README.md';s=p.read_text();addition='''\n## Ridge回帰の実測・予測散布図\n\n- [05：膜単位評価・RGB値](05_Ridge_実測と予測_RGB値.png)\n- [06：膜単位評価・変化量](06_Ridge_実測と予測_変化量.png)\n- [07：過去→今日・RGB値](07_Ridge_実測と予測_RGB値.png)\n- [08：過去→今日・変化量](08_Ridge_実測と予測_変化量.png)\n\n横軸が実測、縦軸が予測、破線はy=x。一点は一つの予測区間で、同じ膜の複数点は独立膜ではない。学習に含めた膜への当てはまりではなく、除外した膜への予測を表示。RGB値そのものは元の色の違いが大きいため、近く見えても変化予測が優れる保証はない。変化量図と単純予測との誤差比較を併せて見る。各色のMAEは膜ごとに等重み。散布図の全座標はridge_scatter_points.csv。\n'''
if '## Ridge回帰の実測・予測散布図' not in s:p.write_text(s+addition)
print(json.dumps(r2_rows,ensure_ascii=False,indent=2))
