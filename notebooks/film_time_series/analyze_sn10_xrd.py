"""Sn10%: six initial/1h XRD scans and three nominal1h images."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import hashlib
import io
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import cv2
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'notebooks/capture_repeatability'))
from analyze_repeatability import corners_and_bbox,roi
BASE=ROOT/'data/raw/Touma/FACsSnPbI3(Sn10mol%)_SnF2_0.1mol%/20261112'
OUT=ROOT/'results/20261112/01_sn10_xrd_image_comparison'
WINDOWS={
    'low':{'search':(12,13),'background':((11.5,11.8),(13.1,13.3))},
    'main':{'search':(13.4,14.7),'background':((13.15,13.35),(14.9,15.2))},
    'high':{'search':(27.5,29.0),'background':((27.0,27.3),(29.2,29.5))}}


def features(x,y,definition):
    smooth=np.convolve(y,np.ones(5)/5,mode='same')
    left,right=[(x>=a)&(x<=b) for a,b in definition['background']]
    bg=np.interp(x,[np.median(x[left]),np.median(x[right])],[np.median(y[left]),np.median(y[right])])
    net=smooth-bg;a,b=definition['search'];mask=(x>=a)&(x<=b)
    indices=np.flatnonzero(mask);index=indices[np.argmax(net[indices])];height=net[index]
    lo=hi=index
    while lo>0 and net[lo]>height/2:lo-=1
    while hi<len(x)-1 and net[hi]>height/2:hi+=1
    valid=(lo<index<hi and x[lo]>=definition['background'][0][0] and x[hi]<=definition['background'][1][1] and height>0)
    if valid:
        xl=float(np.interp(height/2,net[lo:lo+2],x[lo:lo+2]))
        xr=float(np.interp(height/2,net[hi-1:hi+1][::-1],x[hi-1:hi+1][::-1]));width=xr-xl
    else:width=None
    area=float(np.trapezoid(net[mask],x[mask]))
    resolved=bool(valid and index not in (indices[0],indices[-1]) and area>0)
    return {'angle_deg':float(x[index]) if resolved else None,'height_net_cps':float(height),
            'apparent_fwhm_deg':width if resolved else None,'net_area_cps_deg':area,
            'resolved_by_window_rule':resolved}


def scan_metadata(path):
    with zipfile.ZipFile(path) as archive:
        root=ET.fromstring(archive.read('Data0/MesurementConditions0.xml'))
        def value(tag):return next(e.text for e in root.iter() if e.tag.split('}')[-1]==tag)
        meta={name:value(name) for name in ('SystemName','TargetName','WaveType','Current','CurrentUnit','Voltage','VoltageUnit',
              'WavelengthKalpha1','WavelengthKalpha2','AxisName','Step','Speed','SpeedUnit','IntensityUnit','StartTime','EndTime')}
        native=np.loadtxt(io.StringIO(archive.read('Data0/Profile0.txt').decode('utf-8-sig')))
    for kind in ('Start','End'):
        meta[kind+'TimeJST']=datetime.fromisoformat(meta[kind+'Time'].replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Tokyo')).isoformat()
    meta['duration_seconds']=(datetime.fromisoformat(meta['EndTimeJST'])-datetime.fromisoformat(meta['StartTimeJST'])).total_seconds()
    return meta,native


def csv_save(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'image_crops').mkdir(exist_ok=True)
    font=FontProperties(fname='/mnt/c/Windows/Fonts/YuGothR.ttc')
    scans={};metrics=[];timing=[];manifest=[]
    def record(path,kind):
        manifest.append({'kind':kind,'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for minute in (5,10,15):
        for age in ('0h','1h'):
            folder=BASE/'XRD'/f'{minute}min'/age
            txt=next(folder.glob('*.txt'));rasx=next(folder.glob('*.rasx'))
            array=np.loadtxt(txt,skiprows=2,encoding='utf-8-sig');assert array.shape==(5701,2)
            x,y=array.T;assert np.all(np.diff(x)>0)
            meta,native=scan_metadata(rasx)
            assert np.allclose(native[:,0],x) and np.all(native[:,2]==1)
            dwell=float(meta['Step'])/(float(meta['Speed'])/60)
            conversion_error=float(np.max(np.abs(native[:,1]/dwell-y)))
            # TXT export has fewer decimal places at high intensities.
            assert np.allclose(native[:,1]/dwell,y,rtol=1e-6,atol=.001)
            meta['txt_vs_native_counts_to_cps_max_error']=conversion_error
            row={'anneal_min':minute,'elapsed_label':age}
            for name,definition in WINDOWS.items():
                row.update({name+'_'+k:v for k,v in features(x,y,definition).items()})
            row['low_over_main_net_area']=(row['low_net_area_cps_deg']/row['main_net_area_cps_deg']
                if row['low_resolved_by_window_rule'] and row['main_resolved_by_window_rule'] else None)
            metrics.append(row);scans[minute,age]=(x,y,row,meta)
            timing.append({'anneal_min':minute,'elapsed_label':age,**meta})
            record(txt,'xrd_txt');record(rasx,'xrd_rasx')
    image_rows=[];crops=[]
    for minute in (5,10,15):
        image=next((BASE/f'{minute}min/1h').glob('*.jpg'));sidecar=image.with_suffix('.json')
        photo=json.loads(sidecar.read_text());rgb=np.array(Image.open(image).convert('RGB'))
        corners,bbox=corners_and_bbox(rgb);target=np.float32([[0,0],[255,0],[255,255],[0,255]])
        crop=cv2.warpPerspective(rgb,cv2.getPerspectiveTransform(corners,target),(256,256));crops.append(crop)
        Image.fromarray(crop).save(OUT/'image_crops'/f'{minute}min_1h.png')
        pixels=roi(crop,.18).reshape(-1,3)
        x,y,row,meta=scans[minute,'1h']
        start=datetime.fromisoformat(meta['StartTimeJST']);end=datetime.fromisoformat(meta['EndTimeJST'])
        photo_time=datetime.fromisoformat(photo['captured_at'])
        image_row={'anneal_min':minute,'elapsed_label':'1h','image_filename':image.name,
                   'photo_timestamp':photo['captured_at'],'xrd_start_jst':start.isoformat(),
                   'xrd_end_jst':end.isoformat(),'photo_minus_xrd_end_minutes':(photo_time-end).total_seconds()/60,
                   'image_fixed_verified':photo['fixed_settings_verified'],
                   'xrd_low_over_main_net_area':row['low_over_main_net_area'],
                   'xrd_main_angle_deg':row['main_angle_deg'],'xrd_main_apparent_fwhm_deg':row['main_apparent_fwhm_deg']}
        for i,c in enumerate('RGB'):
            image_row['image_mean_'+c]=float(pixels[:,i].mean());image_row['image_spatial_sd_'+c]=float(pixels[:,i].std())
        image_rows.append(image_row);record(image,'photo_1h');record(sidecar,'photo_metadata_1h')
    shifts=[]
    for minute in (5,10,15):
        a=scans[minute,'0h'][2];b=scans[minute,'1h'][2]
        shifts.append({'anneal_min':minute,**{name+'_shift_deg':b[name+'_angle_deg']-a[name+'_angle_deg']
                        if a[name+'_angle_deg'] is not None and b[name+'_angle_deg'] is not None else None for name in WINDOWS},
                       'main_height_change_percent':(b['main_height_net_cps']/a['main_height_net_cps']-1)*100})
    csv_save('xrd_features.csv',metrics);csv_save('scan_metadata.csv',timing)
    csv_save('paired_1h_image_xrd.csv',image_rows);csv_save('time_changes.csv',shifts)
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (OUT/'analysis_config.json').write_text(json.dumps({'sample':'Sn/(Sn+Pb)=0.10; Pb0.90; SnF2 0.1mol% total composition; anneal130C',
        'windows':WINDOWS,'smoothing':'five-point moving average','area':'signed net area over each search window',
        'phase_assignment':None,'instrument_broadening_corrected':False,
        'no_automatic_angle_shift_correction':True,'photo_roi':'corner-aligned256x256,each edge18%removed',
        'physical_same_film_repeated_measurement':'not independently verified; user matched condition/time labels',
        'timestamp_assumption':'RASX Z parsed asUTC and converted toJST; device clock correctness not verified',
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
    fig,axes=plt.subplots(3,2,figsize=(13,10))
    for i,minute in enumerate((5,10,15)):
        for age,color in [('0h','#d78024'),('1h','#246dad')]:
            x,y,row,_=scans[minute,age];smooth=np.convolve(y,np.ones(5)/5,mode='same')
            axes[i,0].plot(x,y,color=color,label=age,lw=.7)
            mask=(x>=13.4)&(x<=14.7);norm=smooth[mask].max()
            axes[i,1].plot(x,smooth/norm,color=color,label=age)
        axes[i,0].set_xlim(3,60);axes[i,0].set_ylabel('測定強度（cps）',fontproperties=font)
        axes[i,0].set_title(f'130℃・{minute}分：生データ',fontproperties=font)
        axes[i,1].set_xlim(11.5,15.3);axes[i,1].set_ylabel('約14°のピーク高さで規格化（背景込み）',fontproperties=font)
        axes[i,1].set_title(f'{minute}分：角度をずらさず比較',fontproperties=font)
        for ax in axes[i]:ax.legend();ax.grid(alpha=.2);ax.set_xlabel('ファイル記載の角度（°）',fontproperties=font)
    fig.suptitle('Sn10%：初期（0h）と公称1hのXRD比較',fontproperties=font,fontsize=17)
    fig.tight_layout(rect=(0,0,1,.95));save(fig,'01_XRD_0hと1h')
    fig,axes=plt.subplots(3,2,figsize=(11,12),gridspec_kw={'width_ratios':[1,1.6]})
    for i,minute in enumerate((5,10,15)):
        axes[i,0].imshow(crops[i]);axes[i,0].add_patch(plt.Rectangle((46,46),164,164,fill=False,color='lime'))
        axes[i,0].set_title(f'{minute}分：公称1h画像',fontproperties=font);axes[i,0].axis('off')
        for age,color in [('0h','#d78024'),('1h','#246dad')]:
            x,y,_,_=scans[minute,age];axes[i,1].plot(x,y,color=color,label=age,lw=.9)
        axes[i,1].set_xlim(10,33);axes[i,1].set_title(f'同じ条件のXRD：{minute}分',fontproperties=font)
        axes[i,1].set_xlabel('角度（°）',fontproperties=font);axes[i,1].set_ylabel('強度（cps）',fontproperties=font)
        axes[i,1].legend();axes[i,1].grid(alpha=.2)
    fig.suptitle('公称1hの画像とXRDを対応付ける（完全な同時測定ではない）',fontproperties=font,fontsize=16)
    fig.tight_layout(rect=(0,0,1,.96));save(fig,'02_1h画像とXRD')
    report(metrics,image_rows,shifts,timing)
    print(OUT)
    for r in metrics:print(r['anneal_min'],r['elapsed_label'],r['main_angle_deg'],round(r['main_apparent_fwhm_deg'],3),r['low_over_main_net_area'])


def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=170,bbox_inches='tight');fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight');plt.close(fig)


def report(metrics,images,shifts,timing):
    def format_value(value,digits=3):return f'{value:.{digits}f}' if value is not None else '抽出不成立'
    lines=['# Sn10%：初期・1hのXRDと画像の対応','',
           '**[XRDの0h・1h比較](01_XRD_0hと1h.png)** と **[1h画像との対応](02_1h画像とXRD.png)** を作りました。','',
           '## 条件と読み込み確認','',
           '- Sn/(Sn+Pb)=0.10、Pb=0.90、SnF₂ 0.1 mol%（全体組成に対して）、130℃アニール5・10・15分。',
           '- 時点表記なし＝成膜直後0h、1h表記＝公称1h。ユーザー確認済みです。',
           '- TXT6個とRASX6個をrawの実験フォルダ内のXRD/アニール時間/経過時間へ移動し、ファイル名と内容は維持しました。xrd_organization.jsonに対応とSHA-256があります。',
           '- RASX記録：Rigaku MiniFlex、Cu Kα、40kV・15mA、3〜60°、0.01°刻み、10°/min。1スキャンは約6分半。',
           '- TXT各5701点。RASXのcountsをStep/Speedで計算した0.06秒で割った値がTXTのcpsと丸め誤差内で一致し、同じ測定の2形式であることを確認しました。','',
           '## まず観察できること','',
           '- 約12〜13°、約14°、約28°にピークが見えます。ここではlow/main/highという角度領域名で数値化し、結晶相名は付けていません。',
           '- アニール条件や時点によって、ピークの相対的な大きさや位置が異なります。強度の変化をそのまま相の割合や劣化率には変換していません。',
           '- 特に10分では複数のピークが同方向へずれて見えます。材料の結晶変化と断定する前に、試料の高さ・セット位置・測定補正などを確認する必要があります。角度を自動的にずらして重ねる処理はしていません。','',
           '| アニール | 時点 | 約14°位置 | 見かけ半値幅 | low/main面積比 |','|---|---|---:|---:|---:|']
    for r in metrics:lines.append(f'| {r["anneal_min"]}分 | {r["elapsed_label"]} | {r["main_angle_deg"]:.2f}° | {r["main_apparent_fwhm_deg"]:.3f}° | {format_value(r["low_over_main_net_area"])} |')
    lines+=['','low/mainは指定角度窓で局所背景を差し引いた信号面積の比です。PbI₂の割合・結晶相の体積比ではありません。5分・1hのlow領域では、窓の端が最大となり面積も負になるため、位置・幅・比を採用しません。抽出不成立は相の不存在の証明ではなく、背景推定や窓の見直しを要することを示します。','',
            '| アニール | lowピークの0→1h移動 | mainピーク移動 | highピーク移動 |','|---|---:|---:|---:|']
    for r in shifts:lines.append(f'| {r["anneal_min"]}分 | {format_value(r["low_shift_deg"],2)} | {format_value(r["main_shift_deg"],2)} | {format_value(r["high_shift_deg"],2)} |')
    lines+=['','一般に試料位置のずれも回折ピーク位置に影響し得ます。[Rigakuの説明](https://rigaku.com/products/x-ray-diffraction-and-scattering/xrd/calculators/bb-peak-shift)。今回のずれの原因を特定したものではありません。','',
            '## 写真とXRDの時刻','',
            'RASXのZ付き時刻をUTCとして日本時間へ変換しました。装置時計そのものの正確さは未確認です。公称0h／1hと、実際の測定時刻を分けて記録しました。','',
            '| アニール | 時点 | XRD開始〜終了（JST） |','|---|---|---|']
    for r in timing:lines.append(f'| {r["anneal_min"]}分 | {r["elapsed_label"]} | {r["StartTimeJST"][11:19]}〜{r["EndTimeJST"][11:19]} |')
    lines+=['','| アニール | 1h画像の時刻 | 1h XRD終了から写真まで |','|---|---|---:|']
    for r in images:lines.append(f'| {r["anneal_min"]}分 | {r["photo_timestamp"][11:19]} | {r["photo_minus_xrd_end_minutes"]:.1f}分 |')
    lines+=['','各画像は同じ公称1hのXRDに対応付けていますが、完全な同時測定ではありません。特に5分条件では時間差が大きく、その間の変化を無視できるとは限りません。','',
            '## このデータの使い道','',
            '1. 同じ条件の0hと1h XRDで、パターンの変化を記述する。',
            '2. 1hの画像特徴と1h XRDの特徴を同じ行に並べる。写真がない5分・10分の0h画像は作らない。',
            '3. 相の帰属を確認した後、画像から予測したい評価を検討する。3膜だけで良否判定モデルや一般的な相関は作らない。','',
            '## 方法と未確認事項','',
            '- XRDは5点移動平均。各ピークの両側の中央値を直線で結ぶ局所背景を使用。探索・背景窓はanalysis_config.jsonを参照。',
            '- 半値幅は装置幅補正・プロファイルフィットなしの見かけ値。強度・面積は配向・膜厚・照射位置などの影響も受けます。',
            '- 写真は基板四隅で位置合わせし、256×256の各辺18%を除く中央領域の平均RGB・画素標準偏差を測定。色補正なし。',
            '- 全測定が同一の物理的な膜の繰り返しか、別の対応試料かは独立に確認できていません。各時点の実測開始・終了と試料の置き方・保存環境も含めて解釈します。',
            '- 0h→1hでピークが変わったというだけでは、化学的劣化や性能低下とは判定しません。','',
            '数値：[XRD特徴](xrd_features.csv)、[画像とXRDの対応](paired_1h_image_xrd.csv)、[測定情報](scan_metadata.csv)、[時点間変化](time_changes.csv)。',
            '入力とSHA-256はinput_manifest.json。再実行：`python3 notebooks/film_time_series/analyze_sn10_xrd.py`。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
