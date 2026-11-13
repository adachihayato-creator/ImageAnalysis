"""Four representative images: 5min/10min, 3h/1day; exploratory JPEG metrics."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from analyze_repeatability import corners_and_bbox, roi

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/raw/Touma/FACsSnPbI3(Sn25mol%)/20261110'
OUT=ROOT/'data/processed/20261111/02_5min_10min_comparison'
INPUTS=[('5min','3h','5min/3h/photo_20261110_190011_602812.jpg'),
        ('5min','1day','5min/1day/01_動かさず5回/photo_20261111_174445_968382.jpg'),
        ('10min','3h','10min/3h/photo_20261110_190136_786693.jpg'),
        ('10min','1day','10min/1day/photo_20261111_181207_039029.jpg')]
PATCHES=[(785,555),(1585,555),(1185,250),(1185,855)]
COLORS=['#cf493f','#278d4f','#426dc9']


def write_csv(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'crops').mkdir(exist_ok=True)
    font_path=Path('/mnt/c/Windows/Fonts/YuGothR.ttc')
    font=FontProperties(fname=str(font_path)) if font_path.exists() else FontProperties()
    rows=[];crops=[];manifest=[];sensitivity=[];grids=[];meta=[];texture_maps=[]
    target=np.float32([[0,0],[255,0],[255,255],[0,255]])
    for condition,elapsed,relative in INPUTS:
        image=BASE/relative;sidecar=image.with_suffix('.json');data=json.loads(sidecar.read_text());meta.append(data)
        rgb=np.array(Image.open(image).convert('RGB'));corners,bbox=corners_and_bbox(rgb)
        transform=cv2.getPerspectiveTransform(corners,target)
        crop=cv2.warpPerspective(rgb,transform,(256,256));crops.append(crop)
        floats=crop.astype(np.float32)
        high=cv2.GaussianBlur(floats,(0,0),.7)-cv2.GaussianBlur(floats,(0,0),3)
        mask=np.zeros(rgb.shape[:2],np.uint8);cv2.fillConvexPoly(mask,corners.astype(np.int32),1)
        paper=[]
        for x,y in PATCHES:
            assert not mask[y-20:y+20,x-20:x+20].any()
            paper.append(rgb[y-20:y+20,x-20:x+20].mean((0,1)))
        paper=np.mean(paper,0)
        row={'condition':condition,'elapsed_label':elapsed,'filename':image.name,
             'captured_at':data['captured_at'],'fixed_verified':data['fixed_settings_verified'],
             'center_x':float(corners[:,0].mean()),'center_y':float(corners[:,1].mean())}
        for margin in (.12,.18,.24):
            pixels=roi(crop,margin).reshape(-1,3);hp=roi(high,margin).reshape(-1,3)
            entry={'condition':condition,'elapsed_label':elapsed,'margin_fraction':margin}
            for j,c in enumerate('RGB'):
                entry['mean_'+c]=float(pixels[:,j].mean())
                entry['spatial_sd_'+c]=float(pixels[:,j].std())
                entry['fine_pattern_sd_'+c]=float(hp[:,j].std())
                if margin==.18:
                    row.update({k:v for k,v in entry.items() if k.endswith('_'+c)})
                    row['paper_'+c]=float(paper[j])
            sensitivity.append(entry)
        hp_roi=roi(high,.18);grid=np.zeros((8,8))
        for y,block in enumerate(np.array_split(hp_roi,8,axis=0)):
            for x,cell in enumerate(np.array_split(block,8,axis=1)):
                grid[y,x]=np.sqrt(np.mean(cell**2))
                grids.append({'condition':condition,'elapsed_label':elapsed,'row':y,'column':x,'fine_pattern_rms':float(grid[y,x])})
        texture_maps.append(grid);rows.append(row)
        Image.fromarray(crop).save(OUT/'crops'/f'{condition}_{elapsed}.png')
        manifest.append({'condition':condition,'elapsed_label':elapsed,'image':str(image.relative_to(ROOT)),
                         'json':str(sidecar.relative_to(ROOT)),
                         'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
                         'json_sha256':hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                         'corners':corners.tolist(),'transform':transform.tolist()})
    hashes={m['fixed_settings']['profile_sha256'] for m in meta};assert len(hashes)==1
    for key in ('ExposureTime','AnalogueGain','ColourGains','LensPosition'):
        assert all(m['settings'][key]==meta[0]['settings'][key] for m in meta)
    for i,row in enumerate(rows):
        baseline=rows[0] if row['condition']=='5min' else rows[2]
        for c in 'RGB':row['background_normalized_'+c]=row['mean_'+c]*baseline['paper_'+c]/row['paper_'+c]
    deltas=[]
    for condition,i,j in [('5min',0,1),('10min',2,3)]:
        entry={'condition':condition,'comparison':'1day minus 3h'}
        for c in 'RGB':
            entry['raw_delta_'+c]=rows[j]['mean_'+c]-rows[i]['mean_'+c]
            entry['background_normalized_delta_'+c]=rows[j]['background_normalized_'+c]-rows[i]['mean_'+c]
        deltas.append(entry)
    write_csv('metrics.csv',rows);write_csv('time_changes.csv',deltas)
    write_csv('roi_sensitivity.csv',sensitivity);write_csv('fine_pattern_grid.csv',grids)
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (OUT/'analysis_config.json').write_text(json.dumps({'primary_margin':.18,'margins':[.12,.18,.24],
        'registration':'detected substrate corners; perspective warp 256x256; not pixel-perfect registration',
        'paper_patch_centers':PATCHES,'paper_patch_size':[40,40],
        'fine_pattern_filter':{'gaussian_sigma_pixels':[.7,3.0],'coordinate_system':'256x256 warped image'},
        'sample_count':'one film per condition assumed from user labels; not replicated films',
        'representative_5min_1day':'first of five fixed images, not selected by appearance',
        'fixed_profile_sha256':next(iter(hashes)),
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
    fig,axes=plt.subplots(2,2,figsize=(9,9))
    for i,ax in enumerate(axes.flat):
        ax.imshow(crops[i]);ax.add_patch(plt.Rectangle((46,46),164,164,fill=False,color='lime',lw=1.3))
        ax.set_title(rows[i]['condition']+'・'+rows[i]['elapsed_label'],fontproperties=font,fontsize=16);ax.axis('off')
    fig.suptitle('4条件の代表写真：位置をそろえて比較／色補正なし',fontproperties=font,fontsize=16)
    fig.text(.5,.01,'緑枠内を数値化。白い位置合わせ枠とは別の「解析領域」です。',ha='center',fontproperties=font)
    fig.tight_layout(rect=(0,.03,1,.96));save(fig,'01_写真4条件')
    fig,axes=plt.subplots(1,3,figsize=(16,5.4))
    labels=[r['condition']+'\n'+r['elapsed_label'] for r in rows]
    for ax,prefix,title in zip(axes,['mean','spatial_sd','fine_pattern_sd'],
                               ['平均色','広い領域の色むら','細かな模様の強さ（参考）']):
        for j,c in enumerate('RGB'):
            ax.bar(np.arange(4)+(j-1)*.24,[r[prefix+'_'+c] for r in rows],width=.24,color=COLORS[j],label=c)
        ax.set_xticks(range(4),labels,fontproperties=font);ax.legend();ax.set_title(title,fontproperties=font)
        ax.set_ylabel('JPEGのRGB単位（％・劣化率ではない）',fontproperties=font);ax.grid(axis='y',alpha=.2)
    fig.suptitle('異なる特徴を別々に測る：どれか1つで良否を決めない',fontproperties=font,fontsize=16)
    fig.tight_layout(rect=(0,0,1,.94));save(fig,'02_色と模様の比較')
    fig,axes=plt.subplots(1,4,figsize=(14,4))
    maximum=max(float(g.max()) for g in texture_maps)
    for i,ax in enumerate(axes):
        im=ax.imshow(texture_maps[i],vmin=0,vmax=maximum,cmap='magma')
        ax.set_title(labels[i].replace('\n','・'),fontproperties=font);ax.set_xticks([]);ax.set_yticks([])
    fig.colorbar(im,ax=list(axes),shrink=.65,label='Fine-pattern RMS (RGB units)')
    fig.suptitle('参考：細かな模様の分布（明るいほど強い／劣化マップではない）',fontproperties=font,fontsize=14)
    save(fig,'03_細かな模様の分布')
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for j,c in enumerate('RGB'):
        axes[0].bar(np.arange(4)+(j-1)*.24,[r['paper_'+c] for r in rows],width=.24,color=COLORS[j],label=c)
    axes[0].set_xticks(range(4),labels,fontproperties=font);axes[0].set_title('背景の紙の平均RGBも変化',fontproperties=font);axes[0].legend()
    for i,d in enumerate(deltas):
        for j,(prefix,label) in enumerate([('raw_delta','補正前'),('background_normalized_delta','背景で簡易補正')]):
            axes[1].bar(np.arange(3)+i*4+(j-.5)*.35,[d[prefix+'_'+c] for c in 'RGB'],width=.35,label=label if i==0 else None)
    axes[1].set_xticks([1,5],['5min：R G B','10min：R G B'],fontproperties=font)
    axes[1].axhline(0,color='gray');axes[1].legend(prop=font)
    axes[1].set_title('1day－3h：背景の扱いで結果が変わる',fontproperties=font)
    axes[1].set_ylabel('RGB変化量',fontproperties=font)
    fig.tight_layout();save(fig,'04_背景の影響_参考')
    report(rows,deltas)
    print(OUT)


def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=165,bbox_inches='tight');fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight');plt.close(fig)


def report(rows,deltas):
    lines=['# 5min・10min：3hと1dayの画像比較','',
           '**最初は [4条件の写真](01_写真4条件.png) と [色・模様のグラフ](02_色と模様の比較.png) を見てください。**','',
           '## 分かったこと','',
           '- **10minの膜は、今回の写真では5minより平均RGBが低く、暗く写っています。** 3h・1dayの両方で見られました。これは画像の違いで、10minの方が良い／悪いという結論ではありません。',
           '- **10minでは細かな粒状模様の指標が高い一方、広い領域の画素標準偏差は必ずしも高くありません。** 広い陰影・反射の影響と細かな模様は別の特徴です。「標準偏差1つ＝均一性の良否」と決めない根拠になります。',
           '- **経時変化には背景の色変化が重なっています。** 5minではR低下・G/B増加、10minではRGB低下が見られますが、背景で簡易補正すると平均色の変化は小さくなります。膜の真の色変化や劣化と断定できません。','',
           '## 数値（代表1枚ずつ、補正前）','',
           '| 条件 | 平均R | 平均G | 平均B | 色むらR | 色むらG | 色むらB |','|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append('| '+r['condition']+'・'+r['elapsed_label']+' | '+' | '.join(f'{r[p+c]:.2f}' for p in ('mean_','spatial_sd_') for c in 'RGB')+' |')
    lines+=['','平均色は解析領域の平均RGB、色むらは同じ領域内の画素標準偏差です。どちらもJPEGのRGB単位で、割合ではありません。','',
            '## 細かな模様の指標','',
            '| 条件 | R | G | B |','|---|---:|---:|---:|']
    for r in rows:lines.append('| '+r['condition']+'・'+r['elapsed_label']+' | '+' | '.join(f'{r["fine_pattern_sd_"+c]:.2f}' for c in 'RGB')+' |')
    lines+=['','256×256へ位置合わせした画像で、ガウシアンぼかしσ0.7とσ3.0の差を計算し、その領域内標準偏差を細かな模様の記述指標としました。空間スケールを仮に決めた探索的指標です。ノイズ・JPEG・ピント・反射にも影響され、結晶粒径や表面粗さを測ったものではありません。',
            '[分布図](03_細かな模様の分布.png)は解析領域を8×8に分割したフィルタ出力のRMS。明るいほどその場所の細かな画像変動が強いことを示し、劣化や膜厚のマップではありません。','',
            '## 3hから1dayの平均色の差と、背景の影響','',
            '| 条件 | 補正前 ΔR / ΔG / ΔB | 背景による簡易補正後 ΔR / ΔG / ΔB |','|---|---|---|']
    for d in deltas:lines.append('| '+d['condition']+' | '+' / '.join(f'{d["raw_delta_"+c]:+.2f}' for c in 'RGB')+' | '+' / '.join(f'{d["background_normalized_delta_"+c]:+.2f}' for c in 'RGB')+' |')
    lines+=['','簡易補正は「膜の平均RGB×その膜の3h背景平均／その画像の背景平均」です。各条件の3hを基準にしています。JPEGの非線形性や照明の空間分布・反射を補償できる保証はありません。補正で差が小さくなったことを、膜に変化がなかった証明とは扱いません。主結果は補正前です。[参考図](04_背景の影響_参考.png)。','',
            '## 比較条件と限界','',
            '- 4枚とも保存設定のハッシュが同じで、露光12.772ms・アナログゲイン・色ゲイン・レンズ位置の記録値が一致しています。設定の一致と光学環境の一致は別です。',
            '- 膜の位置は各写真で違います。10min・1dayでは白枠も5min・1day時点から右40px・下20px移動。3hの撮影は白枠導入前です。照明むら・角度・反射の差が残り得ます。',
            '- 基板の四隅を自動検出して射影変換し、256×256で比較。各辺18%を除く中央を主解析領域としました。12%・24%も感度確認として保存。画素単位の厳密な対応は保証しません。',
            '- 傷や中央の反射らしい領域は除外せず、同じ領域規則で比較しました。実際の膜表面のむらだけを分離した値ではありません。',
            '- 背景は全写真で同じ画像座標の紙4箇所、各40×40px。基板と重ならないことを確認しました。紙の同じ物理位置である保証はありません。',
            '- 5min・1dayは動かさず撮った5枚の最初の1枚を事前方針どおり使用。他の条件も1枚です。繰り返し画像を独立した膜の数とは扱いません。',
            '- 各条件1膜と仮定した探索的比較で、条件差の統計的有意性や一般的な品質順位は示しません。5min／10minがどの工程時間かは未確認です。',
            '- 3h・1dayはユーザー指定ラベル。正確な成膜時刻から経過時間を計算したものではありません。2hは固定前のため今回の比較に含めません。',
            '- 今回の各膜・各時点に対応するXRDや性能の正解データは未対応です。画像だけで結晶相や太陽電池性能、化学的劣化を判定していません。','',
            '## 次に研究で使うなら','',
            '今回区別できた「暗さ」「広い色むら」「細かな模様」を画像特徴の候補として残し、対応するXRDやデバイス性能と照合します。画像の特徴量を1つの良否指標にまとめる段階ではありません。','',
            '数値：[metrics.csv](metrics.csv)、[time_changes.csv](time_changes.csv)、[領域感度](roi_sensitivity.csv)、[分布の数値](fine_pattern_grid.csv)。',
            '再実行：`python3 notebooks/capture_repeatability/compare_conditions.py`。入力の場所とSHA-256はinput_manifest.json、手順はanalysis_config.json。元画像は変更していません。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
