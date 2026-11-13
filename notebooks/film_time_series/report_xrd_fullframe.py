from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import fontManager
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'data/processed/20261113/02_xrd_image_features_fullframe';OLD=ROOT/'data/processed/20261113/01_xrd_image_features';read=lambda f:list(csv.DictReader(f.open(encoding='utf-8-sig')))
full=read(P/'primary_features.csv');central=read(OLD/'primary_features.csv');rows=read(P/'all_feature_sensitivity.csv');comparisons=[];groups={}
for r in rows:
 if float(r['roi_margin'])==0 and r['exclude_central_ellipse']=='False':groups.setdefault((r['background_normalized'],r['local_sigma_px'],r['contrast_threshold']),[]).append(r)
for m in [5,10,15]:
 a=next(r for r in central if r['anneal_min']==str(m));b=next(r for r in full if r['anneal_min']==str(m));comparisons.append({'anneal_min':m,'central_bright_area_percent':float(a['bright_area_percent']),'full_bright_area_percent':float(b['bright_area_percent']),'full_relative_fine_pattern_sd':float(b['relative_fine_pattern_sd']),'full_gray_spatial_cv':float(b['gray_spatial_cv'])})
with (P/'central_vs_full.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
fontManager.addfont('/mnt/c/Windows/Fonts/YuGothR.ttc');plt.rcParams.update({'font.family':'Yu Gothic','font.size':14});fig,ax=plt.subplots(figsize=(9,4.5));x=[0,1,2]
for dx,key,col,label in [(-.18,'central_bright_area_percent','#999999','中央（外周18%除外）'),(.18,'full_bright_area_percent','#dc8a26','基板全体（除外なし）')]:
 ax.bar([i+dx for i in x],[r[key] for r in comparisons],.36,color=col,label=label)
 for i,r in enumerate(comparisons):ax.text(i+dx,r[key]+.3,f'{r[key]:.1f}',ha='center')
ax.set_xticks(x,['5分膜','10分膜','15分膜']);ax.set_ylim(0,23);ax.set_ylabel('局所的に明るい斑点候補の面積 (%)');ax.legend();ax.grid(axis='y',alpha=.2);fig.suptitle('公称1h：外周を含めても15分膜の面積割合が大きい');fig.tight_layout();fig.savefig(P/'04_中央と全体の比較.png',dpi=160,bbox_inches='tight');fig.savefig(P/'04_中央と全体の比較.pdf',bbox_inches='tight');plt.close(fig)
counts={}
for key in ['bright_area_percent','relative_fine_pattern_sd','gray_spatial_cv']:
 counts[key]=sum(float(next(r for r in group if r['anneal_min']=='15')[key])>max(float(r[key]) for r in group if r['anneal_min']!='15') for group in groups.values())
(P/'fullframe_sensitivity_summary.json').write_text(json.dumps({'settings_no_perimeter_or_ellipse_exclusion':len(groups),'15min_largest_count':counts,'not_probabilities':True},ensure_ascii=False,indent=2))
lines=['# 外周を除かない画像特徴とXRDの探索比較','',
'**公称1hの3膜を、切り抜いた基板全体（256×256px）で解析しました。外周も中央楕円も除外していません。** 基板の外側の紙は解析に含めていません。元画像は変更せず、以前の中央領域の結果も残しました。','',
'## 結果','',
'| アニール | 中央領域での斑点候補面積 | 基板全体での斑点候補面積 |','|---|---:|---:|']
for r in comparisons:lines.append(f"| {r['anneal_min']}分 | {r['central_bright_area_percent']:.1f}% | {r['full_bright_area_percent']:.1f}% |")
lines+=['','**外周を含めても15分膜が最大となり、10分膜との差は約4.2ポイント、5分膜との差は約4.0ポイントでした。** 中央だけに限定したために現れた順位ではありません。分母が領域ごとに異なるので、中央と全体の差を外周だけの面積割合と読み替えないでください。','',
'## 見る図','',
'- [基板全体での画像と抽出領域](01_画像特徴の抽出.png)：内部の緑枠はなくし、切り抜き画像の全画素を解析。黄色が斑点候補。',
'- [中央と全体の比較](04_中央と全体の比較.png)：今回の結果が最も分かりやすい図。',
'- [全体での3膜の特徴比較](02_3膜の特徴比較.png)：細かな模様は15分、広い明るさのばらつきは10分が最大。',
'- [対応する公称1h XRD](03_対応するXRD.png)：XRDの解析条件は変更していません。','',
'## 抽出条件への感度','',
'外周0%・楕円除外なしのまま、補正あり/なし×局所平均幅6/8/12px×しきい値5/10/15%の18通りを比較。15分膜が斑点候補面積で最大だったのは18/18、平均明るさで規格化した細かな模様でも18/18。広い明るさのばらつきは0/18で、15分最大ではありませんでした。設定数は独立試料数や正解率ではなく、同じ3膜の計算条件の確認です。','',
'## XRDとの結び付け','',
'約12.7°の副相候補が強い15分膜では、基板全体を使っても明るい斑点候補の面積が大きいという対応が残りました。今回は画像特徴候補としての結果です。副相候補の強い独立膜が1枚であり、斑点がPbI₂である、斑点面積18.3%が副相含有率である、新しい膜を判定できる、とは言えません。','',
'## 方法と注意','',
'同じ元画像・共通の紙RGB補正基準・射影変換・斑点抽出を使用し、主ROIだけを各辺18%除外から0%に変更。主条件の局所平均Gaussianσ8px、相対明暗差10%超、連結3画素以上は維持しました。感度確認用には外周0/12/18/24%、中央楕円の包含/除外も計算しており、全432条件の数値をall_feature_sensitivity.csvに保存。外周なしの主条件はprimary_features.csv、XRDとの対応はpaired_image_xrd.csvです。','',
'基板の四隅で囲まれた全体を使うため、成膜領域に加えて裸のガラス・基板の縁・反射・液だまり・切り抜き誤差が含まれる可能性があります。化学的な膜領域だけのマスクを新たに作った解析ではありません。基板全体と膜そのものを同一視しません。細かな模様は結晶粒径ではありません。','',
'15分膜1hの撮影状態には既知の問題があるため、補正あり/なしでの感度を示し、劣化や相の局所同定は行いません。時計が不正確なXRDはユーザー申告の公称1hとして対応。同一時点の厳密な同時測定を仮定していません。','',
'原本ハッシュ・設定はinput_manifest.jsonとanalysis_config.json。再実行：python3 notebooks/film_time_series/explore_xrd_image_features_fullframe.py → python3 notebooks/film_time_series/report_xrd_fullframe.py。以前の結果は../01_xrd_image_features/に保持。']
(P/'README.md').write_text('\n'.join(lines)+'\n')
f=P.parent/'README.md';s=f.read_text();link='\n[外周を除かない画像特徴の探索比較](02_xrd_image_features_fullframe/README.md)\n';f.write_text(s+link if link not in s else s)
print(comparisons,counts)
