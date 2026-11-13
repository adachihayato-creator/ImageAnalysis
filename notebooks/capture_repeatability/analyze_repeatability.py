"""Descriptive comparison of the 2026-11-10 fixed/repositioned capture test."""
from pathlib import Path
import csv
from datetime import datetime
import hashlib
import json
import platform

import cv2
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/raw/撮影再現性/20261110_FACsSnPbI3_Sn25mol'
OUT = ROOT / 'data/processed/20261110/01_capture_repeatability'
SIZE = 256
MARGINS = (.12, .18, .24)
COLORS = ('#d44b40', '#269753', '#416bc3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corners_and_bbox(rgb):
    h, w = rgb.shape[:2]
    x0, x1, y0, y1 = int(.25*w), int(.75*w), int(.2*h), int(.8*h)
    gray = cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea) + np.array([[[x0, y0]]])
    x, y, width, height = cv2.boundingRect(contour)
    if not (100 < width < 500 and 100 < height < 500 and .7 < width/height < 1.3):
        raise ValueError('Film detection requires manual review')
    hull = cv2.convexHull(contour)
    perimeter = cv2.arcLength(hull, True)
    for fraction in (.01, .015, .02, .03, .04):
        approx = cv2.approxPolyDP(hull, fraction * perimeter, True)
        if len(approx) == 4:
            break
    else:
        raise ValueError('No quadrilateral film detected')
    points = approx[:, 0, :].astype(np.float32)
    sums, diffs = points.sum(axis=1), np.diff(points, axis=1).ravel()
    ordered = np.array([points[sums.argmin()], points[diffs.argmin()],
                        points[sums.argmax()], points[diffs.argmax()]], np.float32)
    if len(np.unique(ordered, axis=0)) != 4:
        raise ValueError('Ambiguous corner ordering')
    return ordered, (x, y, width, height)


def roi(array, margin):
    n = round(SIZE * margin)
    return array[n:SIZE-n, n:SIZE-n]


def savefig(fig, name):
    fig.savefig(OUT / (name + '.png'), dpi=170, bbox_inches='tight')
    fig.savefig(OUT / (name + '.pdf'), bbox_inches='tight')
    plt.close(fig)


def csv_write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'aligned_crops').mkdir(exist_ok=True)
    files = sorted(SOURCE.glob('*/photo_20261110_*.json'), key=lambda p: p.name)
    expected = ['172838','172841','172844','172848','172852','172856','172900',
                '172904','172909','172913','173152','173202','173216','173229',
                '173241','173251','173300','173310','173320','173622']
    # Explicitly freeze this experiment's membership; later captures are excluded.
    files = [f for f in files if f.stem.split('_')[2] in expected]
    if len(files) != 20:
        raise ValueError(f'Expected exactly 20 matched sidecars, got {len(files)}')
    rows, sensitivity, crops, previews, geometries, manifest = [], [], [], [], [], []
    patches = None
    target = np.float32([[0,0], [SIZE-1,0], [SIZE-1,SIZE-1], [0,SIZE-1]])
    initial_time = None
    for i, sidecar in enumerate(files):
        data = json.loads(sidecar.read_text())
        image = sidecar.parent / data['image_filename']
        rgb = np.array(Image.open(image).convert('RGB'))
        corners, (x, y, width, height) = corners_and_bbox(rgb)
        transform = cv2.getPerspectiveTransform(corners, target)
        crop = cv2.warpPerspective(rgb, transform, (SIZE,SIZE))
        crops.append(crop)
        if patches is None:
            cx, cy = x+width/2, y+height/2
            centers = [(cx-1.6*width,cy), (cx+1.6*width,cy), (cx,cy-1.2*height), (cx,cy+1.2*height)]
            patches = [(round(px-20), round(py-20), 40, 40) for px,py in centers]
        bg = []
        contour_mask = np.zeros(rgb.shape[:2],np.uint8)
        cv2.fillConvexPoly(contour_mask, corners.astype(np.int32), 1)
        for px,py,pw,ph in patches:
            if contour_mask[py:py+ph,px:px+pw].any():
                raise ValueError('Film overlaps fixed background patch')
            bg.append(rgb[py:py+ph,px:px+pw].reshape(-1,3).mean(axis=0))
        bg = np.mean(bg,axis=0)
        timestamp = datetime.fromisoformat(data['captured_at'])
        initial_time = initial_time or timestamp
        settings = data['settings']
        group = 'fixed' if i<10 else 'repositioned'
        row = dict(sequence=i+1, group=group, repeat=i%10+1, filename=image.name,
                   captured_at=data['captured_at'], elapsed_seconds=(timestamp-initial_time).total_seconds(),
                   exposure_ms=settings['ExposureTime']/1000,
                   analogue_gain=settings['AnalogueGain'],digital_gain=settings['DigitalGain'],
                   red_gain=settings['ColourGains'][0], blue_gain=settings['ColourGains'][1],
                   lens_position=settings['LensPosition'],
                   sensor_temperature=settings.get('SensorTemperature'),
                   center_x=float(corners[:,0].mean()),center_y=float(corners[:,1].mean()),
                   bbox_width=width,bbox_height=height,
                   angle_degrees=float(np.degrees(np.arctan2(*(corners[1]-corners[0])[::-1]))))
        for margin in MARGINS:
            pixels = roi(crop,margin).reshape(-1,3).astype(float)
            mean, spread = pixels.mean(axis=0), pixels.std(axis=0)
            item = dict(sequence=i+1,group=group,margin_fraction=margin,pixels=len(pixels))
            for j,c in enumerate('RGB'):
                item[f'mean_{c}']=float(mean[j]); item[f'spatial_sd_{c}']=float(spread[j])
                if margin == .18:
                    row[f'mean_{c}']=float(mean[j]);row[f'spatial_sd_{c}']=float(spread[j]);row[f'background_{c}']=float(bg[j])
            sensitivity.append(item)
        rows.append(row)
        geometries.append(dict(filename=image.name,corners=corners.tolist(),transform=transform.tolist(),bbox=[x,y,width,height]))
        overlay=rgb.copy()
        n=round(SIZE*.18)
        boundary=np.float32([[[n,n],[SIZE-n-1,n],[SIZE-n-1,SIZE-n-1],[n,SIZE-n-1]]])
        original_roi=cv2.perspectiveTransform(boundary,np.linalg.inv(transform)).round().astype(np.int32)
        cv2.polylines(overlay,[corners.astype(np.int32)],True,(255,200,0),2)
        cv2.polylines(overlay,[original_roi[0]],True,(0,255,0),2)
        for px,py,pw,ph in patches:cv2.rectangle(overlay,(px,py),(px+pw,py+ph),(0,220,255),2)
        previews.append(overlay)
        Image.fromarray(crop).save(OUT/'aligned_crops'/f'{i+1:02d}_{group}.png')
        manifest.append(dict(image=str(image.relative_to(ROOT)),json=str(sidecar.relative_to(ROOT)),image_sha256=sha(image),json_sha256=sha(sidecar)))
    # Supplementary background normalization; never used as the primary data.
    for row in rows:
        for c in 'RGB':row[f'bg_normalized_{c}']=row[f'mean_{c}']*rows[0][f'background_{c}']/row[f'background_{c}']
    summary=[]
    metrics=['exposure_ms','analogue_gain','digital_gain','red_gain','blue_gain','lens_position',
             'center_x','center_y','angle_degrees']
    metrics += [f'{prefix}_{c}' for prefix in ('mean','spatial_sd','background','bg_normalized') for c in 'RGB']
    for group in ('fixed','repositioned','repositioned_first9'):
        selected=rows[:10] if group=='fixed' else rows[10:19] if group.endswith('first9') else rows[10:]
        for metric in metrics:
            values=np.array([r[metric] for r in selected],float)
            summary.append(dict(group=group,metric=metric,n=len(values),mean=float(values.mean()),
                                sd=float(values.std(ddof=1)),minimum=float(values.min()),maximum=float(values.max()),
                                range=float(np.ptp(values)),cv_percent=float(values.std(ddof=1)/abs(values.mean())*100) if values.mean()!=0 else None))
    csv_write('per_image_metrics.csv',rows); csv_write('group_summary.csv',summary);csv_write('roi_sensitivity.csv',sensitivity)
    (OUT/'analysis_config.json').write_text(json.dumps(dict(sample='FACsSnPbI3(Sn25mol%)',
        film_count=1,group_assignment='first 10 fixed; second 10 repositioned, confirmed in conversation',
        primary_margin=.18,sensitivity_margins=MARGINS,ellipse_exclusion=False,
        background_patches_fixed_image_coordinates=patches,canonical_size=SIZE,
        geometry=geometries,python=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,
        source_code_sha256=sha(Path(__file__))),indent=2),encoding='utf-8')
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # All-image overview, with identical image coordinates and display scaling.
    fig,axes=plt.subplots(4,5,figsize=(16,11))
    for i,ax in enumerate(axes.flat):
        ax.imshow(previews[i]);ax.set_xlim(600,1550);ax.set_ylim(1000,150)
        ax.set_title(f'{i+1:02d} {rows[i]["group"]}\n{rows[i]["captured_at"][11:19]}',fontsize=10);ax.axis('off')
    fig.suptitle('Yellow: film boundary | Green: measured film ROI | Cyan: fixed paper patches')
    fig.tight_layout();savefig(fig,'01_regions_and_positions')
    fig,axes=plt.subplots(4,5,figsize=(14,12))
    for i,ax in enumerate(axes.flat):
        ax.imshow(crops[i]);n=round(SIZE*.18)
        ax.add_patch(plt.Rectangle((n,n),SIZE-2*n,SIZE-2*n,fill=False,color='lime',lw=1))
        ax.set_title(f'{i+1:02d} {rows[i]["group"]}',fontsize=10);ax.axis('off')
    fig.suptitle('Aligned by detected substrate corners; original JPEG colors, no color correction')
    fig.tight_layout();savefig(fig,'02_aligned_film_comparison')
    def plot_metric(ax,keys,labels=None,colors=None):
        for j,key in enumerate(keys):
            label=labels[j] if labels else key
            for sl,marker in ((slice(0,10),'o'),(slice(10,20),'s')):
                ax.plot(np.arange(1,21)[sl],[r[key] for r in rows[sl]],marker=marker,ms=4,
                        color=colors[j] if colors else f'C{j}',label=label if sl.start==0 else None)
        ax.axvline(10.5,color='gray',ls=':');ax.grid(alpha=.25);ax.set_xlabel('Capture number (1-10 fixed; 11-20 repositioned)')
        ax.legend(fontsize=8)
    fig,axes=plt.subplots(3,2,figsize=(14,12))
    for ax,keys,title in zip(axes.flat,[['exposure_ms'],['analogue_gain','digital_gain'],['red_gain','blue_gain'],['lens_position'],['sensor_temperature'],['elapsed_seconds']],
                             ['Exposure time (ms)','Gain (x)','White-balance gains (x)','LensPosition (reported value)','Sensor temperature (C)','Elapsed time (s), showing the final gap']):
        plot_metric(ax,keys);ax.set_title(title)
    fig.tight_layout();savefig(fig,'03_camera_settings')
    fig,axes=plt.subplots(2,2,figsize=(14,10))
    for ax,prefix,title in zip(axes.flat,['mean','spatial_sd','background','bg_normalized'],
                              ['Film mean RGB (0-255)','Within-film spatial SD (texture / unevenness)',
                               'Fixed paper patches: mean RGB (0-255)','Supplement only: film means normalized by paper']):
        plot_metric(ax,[f'{prefix}_{c}' for c in 'RGB'],list('RGB'),COLORS);ax.set_title(title)
    fig.tight_layout();savefig(fig,'04_color_and_unevenness')
    fig,axes=plt.subplots(1,3,figsize=(16,4.7))
    for group,sl,marker in [('fixed',slice(0,10),'o'),('repositioned',slice(10,20),'s')]:
        axes[0].plot([r['center_x'] for r in rows[sl]],[r['center_y'] for r in rows[sl]],marker+'-',label=group)
    axes[0].invert_yaxis();axes[0].set_aspect('equal',adjustable='datalim');axes[0].legend();axes[0].set_title('Detected film center (image pixels)')
    axes[0].set_xlabel('x');axes[0].set_ylabel('y')
    plot_metric(axes[1],['angle_degrees']);axes[1].set_title('Top-edge angle (degrees)')
    plot_metric(axes[2],['bbox_width','bbox_height']);axes[2].set_title('Detected bounding-box size (pixels)')
    fig.tight_layout();savefig(fig,'05_position_variation')
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for ax,prefix,title in zip(axes,['mean','spatial_sd'],['Temporal SD of mean RGB','Temporal SD of spatial unevenness SD']):
        for j,group in enumerate(('fixed','repositioned')):
            values=[next(s['sd'] for s in summary if s['group']==group and s['metric']==f'{prefix}_{c}') for c in 'RGB']
            ax.bar(np.arange(3)+(j-.5)*.35,values,width=.35,label=group)
        ax.set_xticks(range(3),list('RGB'));ax.set_ylabel('SD across 10 images (RGB units)');ax.set_title(title);ax.legend()
    fig.suptitle('Descriptive repeatability; one film, sequential groups, no pass/fail threshold')
    fig.tight_layout();savefig(fig,'06_repeatability_summary')
    make_intro_figure(rows, summary, crops)
    write_report(rows,summary)
    print(OUT)


def make_intro_figure(rows,summary,crops):
    font_path=Path('/mnt/c/Windows/Fonts/YuGothR.ttc')
    font=FontProperties(fname=str(font_path)) if font_path.exists() else FontProperties(family='sans-serif')
    fig=plt.figure(figsize=(13,9))
    grid=fig.add_gridspec(2,2)
    for i,index in enumerate((0,10)):
        ax=fig.add_subplot(grid[0,i]);ax.imshow(crops[index]);n=round(SIZE*.18)
        ax.add_patch(plt.Rectangle((n,n),SIZE-2*n,SIZE-2*n,fill=False,color='lime',lw=2))
        ax.set_title(('動かさない撮影：1枚目' if i==0 else '置き直し撮影：1枚目')+'\n緑の枠内を測定',fontproperties=font,fontsize=13);ax.axis('off')
    ax=fig.add_subplot(grid[1,0])
    for j,(group,label) in enumerate((('fixed','動かさない10枚'),('repositioned','置き直し10枚'))):
        values=[next(s['sd'] for s in summary if s['group']==group and s['metric']==f'mean_{c}') for c in 'RGB']
        ax.bar(np.arange(3)+(j-.5)*.36,values,width=.36,label=label)
    ax.set_xticks(range(3),list('RGB'));ax.set_ylabel('撮るたびの平均色のばらつき（標準偏差）',fontproperties=font)
    ax.set_title('① 棒が高いほど、撮るたびに平均色が変わる',fontproperties=font,fontsize=12)
    ax.legend(prop=font);ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
    ax=fig.add_subplot(grid[1,1])
    for start,end,color,label in ((0,10,'C0','動かさない'),(10,20,'C1','置き直し')):
        ax.plot(range(start+1,end+1),[r['exposure_ms'] for r in rows[start:end]],'o-',color=color,label=label)
    ax.axvline(10.5,color='gray',ls=':');ax.set_xlabel('撮影順：1〜10枚目／11〜20枚目',fontproperties=font)
    ax.set_ylabel('光を取り込む時間（ms）',fontproperties=font);ax.set_title('② 露光時間は一定ではなかった',fontproperties=font,fontsize=12)
    ax.legend(prop=font);ax.grid(alpha=.2)
    fig.suptitle('撮影再現性の確認：同じ膜を20回撮影',fontproperties=font,fontsize=19)
    fig.text(.5,.015,'膜の位置をそろえて比較。色の補正なし。今回の1膜での結果で、良い膜・悪い膜の判定ではありません。',ha='center',fontproperties=font,fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.95));savefig(fig,'00_まず見る結果')


def write_report(rows,summary):
    def stat(group,metric):return next(s for s in summary if s['group']==group and s['metric']==metric)
    lines=['# 撮影再現性の比較：2026-11-10', '',
           '**まずは [日本語の結果図](00_まず見る結果.png) と [図の読み方](00_図の見方.md) だけ見てください。他の図は詳細確認用です。**', '',
           '試料はFACsSnPbI3（Sn25mol%）の同じ1膜。ユーザーの申告に基づき、前半10枚を動かさない撮影、後半10枚を置き直し撮影として比較しました。試料の品質や化学的劣化は判定していません。', '',
           '## 今回分かったこと', '',
           '- 露光・色ゲイン・焦点の設定値は固定されていませんでした。装置形状の評価と並行して、これらの固定と実値確認を進める根拠が得られました。',
           '- 位置をそろえて測った平均RGBの撮影間SDは、今回の2群でほぼ同程度でした。置き直しで平均色のばらつきが大幅に増えたとはいえません。12%・24%の外周除外でも、SD比はR約0.98〜1.00、G約1.09〜1.11、B約1.00でした。',
           '- 置き直しでは画像内の位置が明らかに変わりました。位置決めトレーは位置の再現に有効と考えられますが、それでRGBがどれだけ改善するかは次の試験で確かめます。',
           '- 良否を分けたい実際の膜の差をまだ測っていないため、約0.6〜1.3RGB単位の撮影間SDが十分小さいかは判定できません。', '',
           '## 図を見る', '',
           '- [最初に見る：ばらつきの比較](06_repeatability_summary.png)',
           '- [撮影設定の変動](03_camera_settings.png)',
           '- [色・むら・背景の変動](04_color_and_unevenness.png)',
           '- [解析領域と元画像の位置](01_regions_and_positions.png)',
           '- [位置をそろえた膜20枚](02_aligned_film_comparison.png)',
           '- [位置・角度の変動](05_position_variation.png)', '',
           '図は英語表記です。fixedは動かさない10枚、repositionedは置き直した10枚。各図のPDFも同名で保存しています。', '',
           '## 撮影設定の結果', '',
           '| 項目 | 動かさない10枚：最小〜最大 | 置き直し10枚：最小〜最大 |',
           '|---|---:|---:|']
    for metric,label in [('exposure_ms','露光時間 ms'),('analogue_gain','アナログゲイン'),('digital_gain','デジタルゲイン'),('red_gain','赤の色ゲイン'),('blue_gain','青の色ゲイン'),('lens_position','レンズ位置（記録値）')]:
        a,b=stat('fixed',metric),stat('repositioned',metric)
        lines.append(f'| {label} | {a["minimum"]:.4f}〜{a["maximum"]:.4f} | {b["minimum"]:.4f}〜{b["maximum"]:.4f} |')
    lines += ['', '露光・色ゲイン・レンズ位置が変動しています。今回は固定条件の試験ではなく、既存の自動調整を含む撮影手順全体の再現性試験です。レンズ位置から試料の高さを逆算したり、膜厚を求めたりはしていません。', '',
              '## 画像評価の結果', '',
              '下記のSDは各群10枚の「平均色」の標本標準偏差です。膜内の画素の標準偏差とは別です。単位はJPEGのRGB値（0〜255）。', '',
              '| 成分 | 動かさない：平均 ± 撮影間SD | 置き直し：平均 ± 撮影間SD | SDの比（置き直し／固定） |',
              '|---|---:|---:|---:|']
    for c in 'RGB':
        a,b=stat('fixed',f'mean_{c}'),stat('repositioned',f'mean_{c}')
        lines.append(f'| {c} | {a["mean"]:.3f} ± {a["sd"]:.3f} | {b["mean"]:.3f} ± {b["sd"]:.3f} | {b["sd"]/a["sd"]:.2f} |')
    lines += ['', '膜内の「色むら」は各画像の解析領域内の画素標準偏差で表しました。これは反射・傷・模様・ノイズも含む記述指標で、膜厚むらや品質そのものではありません。', '',
              '| 成分 | 色むら指標：動かさない 平均 ± 撮影間SD | 置き直し 平均 ± 撮影間SD |',
              '|---|---:|---:|']
    for c in 'RGB':
        a,b=stat('fixed',f'spatial_sd_{c}'),stat('repositioned',f'spatial_sd_{c}')
        lines.append(f'| {c} | {a["mean"]:.3f} ± {a["sd"]:.3f} | {b["mean"]:.3f} ± {b["sd"]:.3f} |')
    lines += ['', '## 位置の変動', '']
    for group,label in [('fixed','動かさない'),('repositioned','置き直し')]:
        x,y=stat(group,'center_x'),stat(group,'center_y')
        lines.append(f'- {label}：検出中心のx最大差 {x["range"]:.2f}px、y最大差 {y["range"]:.2f}px。境界検出誤差も含み、校正した機械変位ではありません。')
    lines += ['', '## 最後の1枚を除いた感度確認', '',
              '最後の写真は17:36:22で、直前から約182秒空いています。時間ドリフトと区別できないため、置き直し最初の9枚でも集計しました。最後の写真を主解析から除外はしていません。', '',
              '| 成分 | 置き直し10枚の平均色SD | 置き直し最初9枚の平均色SD |',
              '|---|---:|---:|']
    for c in 'RGB':lines.append(f'| {c} | {stat("repositioned",f"mean_{c}")["sd"]:.3f} | {stat("repositioned_first9",f"mean_{c}")["sd"]:.3f} |')
    lines += ['', '## 方法・解釈の限界', '',
              '- 補正前JPEGをRGBとして読み、暗い基板の四隅を自動検出し、256×256へ射影変換しました。元画像と輪郭の確認図を保存しています。膜上の特徴を画素単位で完全に一致させた保証はありません。',
              '- 主解析領域は基板の各辺から18%を除く中央約64%×64%。以前の解析との比較のため暫定的に同じ割合を採用し、12%・24%も roi_sensitivity.csv に保存しました。最適化した値ではありません。',
              '- 中央の映り込みや傷らしい領域は除外していません。両群で同じ領域規則を使い、実際の評価値の変動を見る試験です。',
              '- 背景は最初の画像で決めた紙上の4領域（各40×40px）を、全画像の同じ画像座標で測定。膜と重ならないことを確認しました。紙の同じ物理点である保証はなく、陰影・紙の位置の影響も含みます。',
              '- 主結果は背景補正なしです。参考として各色の膜平均×最初の背景平均／その画像の背景平均も表示します。この単純なJPEG補正は真の色校正ではなく、背景によって変動が除去できると仮定していません。',
              '- 固定群35秒、置き直し群約270秒の連続した別時間帯です。群差には時刻、自動調整、照明、実際の膜変化が混ざり得ます。置き直しだけの因果効果や独立した誤差成分は算出できません。',
              '- 1膜・1回の試験です。SD比は記述比較であり、統計的有意差や一般的な装置精度を示しません。良い膜／悪い膜の閾値も設定していません。', '',
              '## 次の改善と確認', '',
              '1. 基準試料・照明を固定して撮影設定を決め、露光・色ゲイン・焦点を保存・固定する機能を実装し、画像ごとの実値で検証する。',
              '2. 同じ位置・向き・高さへ戻せる試料トレーを用意する。レンズ／照明の反射については、固定設定下で光学配置を比較する。',
              '3. 改善後に同じ試験を行う。可能なら固定と置き直しを交互に短いブロックで実施し、時間帯の差を小さくする。安定した参照物も一緒に写す。',
              '4. ToF等の追加センサーは、このデータだけでは採否を決められない。測りたい物理量と必要精度を別途決め、交換可能な設計を検討する。', '',
              '## 数値と再実行', '',
              '- [画像ごとの数値](per_image_metrics.csv)',
              '- [群別集計](group_summary.csv)',
              '- [領域の感度確認](roi_sensitivity.csv)',
              '- [解析設定と検出座標](analysis_config.json)',
              '- [入力ファイルとSHA-256](input_manifest.json)', '',
              'リポジトリのルートで `python3 notebooks/capture_repeatability/analyze_repeatability.py` を実行します。NumPy、Pillow、OpenCV、Matplotlibが必要です。元データの内容は変更せず、保存場所を `data/raw/撮影再現性/20261110_FACsSnPbI3_Sn25mol/` の2群に整理しました。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':main()
