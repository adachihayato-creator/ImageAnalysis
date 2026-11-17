"""Compare five fixed and five repositioned 5min/1day images (2026-11-11)."""
from pathlib import Path
import csv
import hashlib
import json
from datetime import datetime

import cv2
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

from analyze_repeatability import corners_and_bbox, roi

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/raw/Touma/FACsSnPbI3(Sn25mol%)/20261110/5min/1day'
OUT=ROOT/'results/20261111/01_fixed_guide_repeatability'
PAPER_PATCHES=[(785,555),(1585,555),(1185,250),(1185,855)]
COLORS=['#ce453c','#24934e','#356cc8']


def csv_save(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'aligned_crops').mkdir(exist_ok=True)
    files=sorted(SOURCE.glob('*/*.json'),key=lambda p:p.name)
    assert len(files)==10
    rows=[];sensitivity=[];crops=[];manifest=[];metadata=[]
    target=np.float32([[0,0],[255,0],[255,255],[0,255]])
    for i,sidecar in enumerate(files):
        data=json.loads(sidecar.read_text());metadata.append(data)
        image=sidecar.parent/data['image_filename'];rgb=np.array(Image.open(image).convert('RGB'))
        h,w=rgb.shape[:2];corners,bbox=corners_and_bbox(rgb)
        guide=np.array(data['position_guide']['profile']['corners_normalized'],np.float32)*np.float32([w-1,h-1])
        transform=cv2.getPerspectiveTransform(corners,target)
        crop=cv2.warpPerspective(rgb,transform,(256,256));crops.append(crop)
        guide_crop=cv2.warpPerspective(rgb,cv2.getPerspectiveTransform(guide,target),(256,256))
        mask=np.zeros(rgb.shape[:2],np.uint8);cv2.fillConvexPoly(mask,corners.astype(np.int32),1)
        paper=[]
        for x,y in PAPER_PATCHES:
            assert not mask[y-20:y+20,x-20:x+20].any()
            paper.append(rgb[y-20:y+20,x-20:x+20].mean((0,1)))
        paper=np.mean(paper,axis=0)
        s=data['settings'];group='fixed' if i<5 else 'repositioned'
        assert data['fixed_settings_verified'] and data['position_guide']['state']=='registered'
        row={'sequence':i+1,'group':group,'filename':image.name,'captured_at':data['captured_at'],
             'exposure_ms':s['ExposureTime']/1000,'analogue_gain':s['AnalogueGain'],
             'digital_gain':s['DigitalGain'],'red_gain':s['ColourGains'][0],'blue_gain':s['ColourGains'][1],
             'lens_position':s['LensPosition'],'sensor_temperature_C':s.get('SensorTemperature'),
             'center_x':float(corners[:,0].mean()),'center_y':float(corners[:,1].mean()),
             'guide_dx':float(corners[:,0].mean()-guide[:,0].mean()),
             'guide_dy':float(corners[:,1].mean()-guide[:,1].mean())}
        for method,arr in [('tracked',crop),('fixed_guide',guide_crop)]:
            for margin in (.12,.18,.24):
                pixels=roi(arr,margin).reshape(-1,3).astype(float)
                item={'sequence':i+1,'group':group,'method':method,'margin_fraction':margin}
                for j,c in enumerate('RGB'):
                    item[f'mean_{c}']=float(pixels[:,j].mean());item[f'spatial_sd_{c}']=float(pixels[:,j].std())
                    if margin==.18:
                        row[f'{method}_mean_{c}']=item[f'mean_{c}']
                        row[f'{method}_spatial_sd_{c}']=item[f'spatial_sd_{c}']
                sensitivity.append(item)
        for j,c in enumerate('RGB'):row[f'paper_{c}']=float(paper[j])
        rows.append(row)
        Image.fromarray(crop).save(OUT/'aligned_crops'/f'{i+1:02d}_{group}.png')
        manifest.append({'image':str(image.relative_to(ROOT)),'json':str(sidecar.relative_to(ROOT)),
                         'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
                         'json_sha256':hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                         'corners':corners.tolist(),'transform':transform.tolist()})
    for key in ('ExposureTime','AnalogueGain','DigitalGain','ColourGains','LensPosition'):
        assert all(d['settings'][key]==metadata[0]['settings'][key] for d in metadata)
    assert len({d['fixed_settings']['profile_sha256'] for d in metadata})==1
    assert len({d['position_guide']['profile_sha256'] for d in metadata})==1
    ccm_same=all(d['metadata'].get('ColourCorrectionMatrix')==metadata[0]['metadata'].get('ColourCorrectionMatrix') for d in metadata)
    summary=[]
    for group,sl in [('fixed',slice(0,5)),('repositioned',slice(5,10))]:
        for key in rows[0]:
            if key in ('sequence','group','filename','captured_at'):continue
            vals=np.array([r[key] for r in rows[sl]],float)
            summary.append({'group':group,'metric':key,'n':5,'mean':float(vals.mean()),
                            'sd':float(vals.std(ddof=1)),'min':float(vals.min()),'max':float(vals.max()),'range':float(np.ptp(vals))})
    csv_save('per_image_metrics.csv',rows);csv_save('group_summary.csv',summary);csv_save('roi_sensitivity.csv',sensitivity)
    config={'condition':'5min','elapsed_time_label':'1day','film_count':1,'group_size':5,
            'primary_method':'tracked corners, warp256, each-edge18% removed; no color correction',
            'sensitivity_methods':['fixed_guide'],'margins':[.12,.18,.24],
            'paper_patch_centers':PAPER_PATCHES,'paper_patch_size':[40,40],
            'ccm_identical':ccm_same,'fixed_profile_sha256':metadata[0]['fixed_settings']['profile_sha256'],
            'guide_profile_sha256':metadata[0]['position_guide']['profile_sha256'],
            'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'analysis_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    fontpath=Path('/mnt/c/Windows/Fonts/YuGothR.ttc')
    font=FontProperties(fname=str(fontpath)) if fontpath.exists() else FontProperties()
    fig,axes=plt.subplots(2,2,figsize=(13,9))
    for ax,prefix,title in [(axes[0,0],'tracked_mean','① 同じ膜の平均色：設定が同じでも変動'),
                            (axes[0,1],'paper','② 背景の紙の色も変動')]:
        for j,c in enumerate('RGB'):
            for lo,hi,marker in [(0,5,'o'),(5,10,'s')]:
                ax.plot(range(lo+1,hi+1),[r[f'{prefix}_{c}'] for r in rows[lo:hi]],marker+'-',color=COLORS[j],label=c if lo==0 else None)
        ax.axvline(5.5,color='gray',ls=':');ax.grid(alpha=.2);ax.legend()
        ax.set_title(title,fontproperties=font);ax.set_ylabel('平均RGB値（0〜255）',fontproperties=font)
        ax.set_xlabel('1〜5枚：動かさない／6〜10枚：置き直し',fontproperties=font)
    for j,(group,label) in enumerate([('fixed','動かさない5枚'),('repositioned','置き直し5枚')]):
        vals=[next(s['sd'] for s in summary if s['group']==group and s['metric']==f'tracked_mean_{c}') for c in 'RGB']
        axes[1,0].bar(np.arange(3)+(j-.5)*.36,vals,width=.36,label=label)
    axes[1,0].set_xticks(range(3),list('RGB'));axes[1,0].legend(prop=font)
    axes[1,0].set_ylabel('撮影間の標準偏差：RGB単位、％ではない',fontproperties=font)
    axes[1,0].set_title('③ 青成分は置き直し群で変動が大きい',fontproperties=font)
    axes[1,0].grid(axis='y',alpha=.2)
    for group,sl,marker,label in [('fixed',slice(0,5),'o','動かさない'),('repositioned',slice(5,10),'s','置き直し')]:
        axes[1,1].plot([r['guide_dx'] for r in rows[sl]],[r['guide_dy'] for r in rows[sl]],marker+'-',label=label)
    axes[1,1].axvline(0,color='gray',ls=':');axes[1,1].axhline(0,color='gray',ls=':')
    axes[1,1].invert_yaxis();axes[1,1].set_aspect('equal',adjustable='datalim');axes[1,1].legend(prop=font)
    axes[1,1].set_title('④ 白枠の中心からのずれ（画像のpx）',fontproperties=font)
    axes[1,1].set_xlabel('右が＋／左が－',fontproperties=font);axes[1,1].set_ylabel('下が＋／上が－',fontproperties=font)
    fig.suptitle('5min・1day：固定設定と白枠を使った撮影の確認',fontproperties=font,fontsize=17)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(OUT/'00_まず見る結果.png',dpi=170);fig.savefig(OUT/'00_まず見る結果.pdf');plt.close(fig)
    fig,axes=plt.subplots(2,5,figsize=(14,6))
    for i,ax in enumerate(axes.flat):
        ax.imshow(crops[i]);ax.add_patch(plt.Rectangle((46,46),164,164,fill=False,color='lime'))
        ax.set_title(f'{i+1} '+('動かさない' if i<5 else '置き直し'),fontproperties=font);ax.axis('off')
    fig.suptitle('位置をそろえた10枚：緑枠内を測定、色補正なし',fontproperties=font,fontsize=16)
    fig.tight_layout();fig.savefig(OUT/'01_膜10枚.png',dpi=160);plt.close(fig)
    report(rows,summary,config)
    print(OUT)


def report(rows,summary,config):
    def s(group,metric):return next(r for r in summary if r['group']==group and r['metric']==metric)
    lines=['# 5min・1day：固定設定と白枠導入後の確認','',
           '**[まず見る結果](00_まず見る結果.png)** と [膜10枚の比較](01_膜10枚.png) を用意しました。', '',
           '## 分かったこと', '',
           '1. **カメラ設定の固定は成功**：10枚すべてで露光12.772ms、アナログ／デジタルゲイン、赤・青の色ゲイン、レンズ位置が同一。保存設定と登録白枠のハッシュも共通でした。色変換行列も同一です。',
           '2. **設定が同じでも、画像の色は一定ではありません**。特に置き直し群の青成分の撮影間SDが大きく、背景の紙でも青・緑成分の変動が見られました。',
           '3. **今回の位置ずれは前回より小さい値でした**。ただし日付・膜状態・枚数・操作の慣れなどが違うため、白枠だけによる改善とは断定しません。', '',
           '## 平均色の撮影間のばらつき', '',
           '膜の四隅で位置をそろえ、各辺18%を除く中央領域を測定。色補正はしていません。SDは5枚の平均色の標本標準偏差で、1枚の中の色むらとは別の量です。', '',
           '| 成分 | 動かさない：平均 ± 撮影間SD | 置き直し：平均 ± 撮影間SD |','|---|---:|---:|']
    for c in 'RGB':
        a,b=s('fixed','tracked_mean_'+c),s('repositioned','tracked_mean_'+c)
        lines.append(f'| {c} | {a["mean"]:.2f} ± {a["sd"]:.2f} | {b["mean"]:.2f} ± {b["sd"]:.2f} |')
    lines+=['','## 位置のばらつき','','| 方法 | 中心xの最大差 | 中心yの最大差 |','|---|---:|---:|']
    for group,label in [('fixed','動かさない5枚'),('repositioned','置き直し5枚')]:
        lines.append(f'| {label} | {s(group,"center_x")["range"]:.2f}px | {s(group,"center_y")["range"]:.2f}px |')
    lines+=['','参考：11月10日の置き直し10枚ではx71.00px、y42.25pxでした。境界検出誤差を含む画像座標であり、校正した機械変位ではありません。枚数が違うので最大差の比を装置の改善率とは扱いません。','',
            '## 次に何を確認するか','',
            '- 設定を膜ごとに変更する必要はありません。今の共通設定と白枠を維持します。',
            '- 背景でも色変動があるため、照明の状態、点灯後の経過時間、外光、置き直し時の反射・影を調べます。写真だけでLEDが原因だとは断定できません。',
            '- 記録されたセンサー温度は61〜76℃で、時間とともに上昇しました。これは膜の温度ではありません。起動・点灯後のウォームアップの影響を確認する根拠にはなりますが、色変動の原因だとは断定しません。',
            '- 次回は機器と照明を一定時間動かして状態を確認してから、紙などの安定した参照物を動かさず撮影します。必要ならLEDの制御方法・給電を確認します。', '',
            '## 図の読み方','',
            '- 左上：膜の平均RGB。赤・緑・青の線は各成分。横軸1〜5枚は動かさない群、6〜10枚は置き直し群。点の間隔は撮影順で、実際の時間間隔ではありません。',
            '- 右上：背景の紙の同じ画像座標4箇所の平均RGB。紙が白いままでも、撮影条件で値が変わり得ます。紙自体の移動も未確認です。',
            '- 左下：撮影間SD。棒が高いほど撮影ごとの平均色が変わります。単位はRGB値で、％や劣化率ではありません。',
            '- 右下：白枠中心からのずれ。原点に近いほど中心が合っています。四隅・高さ・傾き・表裏の一致を保証する図ではありません。', '',
            '## 限界・方法','',
            '- 同じ1膜・各5枚の記述比較です。固定群約21秒、置き直し群約84秒で、時間帯も違います。置き直しだけの因果効果や統計的有意差を示しません。',
            '- 1dayはユーザー指定の経過時間ラベルで、成膜時刻から厳密な24時間を計算したものではありません。',
            '- 1dayと前日の色の差は、本試験では材料劣化として評価しません。撮影条件や膜の状態が違うためです。',
            '- 色むら指標もCSVに保存しました。反射・傷・模様・ノイズを含み、膜厚や良否の直接測定ではありません。',
            '- 位置合わせは自動検出した基板四隅による射影変換（256×256）。四隅の検出誤差・補間の影響が残ります。',
            '- 対照として白枠座標の固定ROIでも計算しました。主要傾向は同様で、青の撮影間SDは固定ROIで約0.98／2.56、追従ROIで約0.97／2.54です。',
            '- 外周12%・18%・24%と、追従ROI／白枠固定ROIの両方をroi_sensitivity.csvに保存。18%は以前と同じ暫定条件で、最適値ではありません。',
            '- 背景は紙上の40×40pxを4箇所、全写真で同じ画像座標で測定。基板と重ならないことを確認しました。原画像は変更していません。','',
            '## 保存したデータ','',
            '- [各画像の数値](per_image_metrics.csv)','- [群別集計](group_summary.csv)',
            '- [解析領域の感度](roi_sensitivity.csv)','- [入力と検出座標](input_manifest.json)',
            '- [解析設定](analysis_config.json)','',
            '再実行：`python3 notebooks/capture_repeatability/analyze_fixed_guide.py`。NumPy、Pillow、OpenCV、Matplotlibが必要です。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
