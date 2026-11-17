"""Worked example: pair initial images with descriptive initial XRD features."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from xrd_image_comparison import FILES, feature14, peak

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/20261015/06_xrd_image_practice'
IMAGES={
    'BrRb_1':'Tuji/FACsPbI3_BrRb_5mol_per_gram/1枚目0h.jpg',
    'BrRb_2':'Tuji/FACsPbI3_BrRb_5mol_per_gram/2枚目0h.jpg',
    'Sn25_1':'Touma/FACsSnPbI3(Sn25mol%)/1枚目0h.jpg',
    'Sn25_2':'Touma/FACsSnPbI3(Sn25mol%)/2枚目0h.jpg'}


def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=170,bbox_inches='tight')
    fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight');plt.close(fig)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fontpath=Path('/mnt/c/Windows/Fonts/YuGothR.ttc')
    font=FontProperties(fname=str(fontpath)) if fontpath.exists() else FontProperties()
    temporal_path=ROOT/'results/20261015/05_image_time_series_0to24h/aligned_rgb.csv'
    temporal=list(csv.DictReader(temporal_path.open(encoding='utf-8-sig')))
    data={};rows=[];manifest=[]
    for tag,relative in FILES.items():
        xrd_path=ROOT/'data/raw'/relative
        array=np.loadtxt(xrd_path,skiprows=2,encoding='utf-8-sig');x,y=array.T
        assert array.shape==(5701,2) and np.all(np.diff(x)>0)
        location,width,height,bg=feature14(x,y)
        smooth=np.convolve(y,np.ones(5)/5,mode='same');net=smooth-bg
        window=(x>=13.4)&(x<=14.4)
        image_path=ROOT/'results/20261015/01_crops'/IMAGES[tag]
        image=np.array(Image.open(image_path).convert('RGB'));h,w=image.shape[:2]
        mx,my=round(w*.18),round(h*.18)
        pixels=image[my:h-my,mx:w-mx].reshape(-1,3)
        t=next(r for r in temporal if r['sample']==tag and r['hour']=='3' and r['reflection_excluded']=='False')
        row={'sample':tag,'composition_group':'BrRb' if tag.startswith('BrRb') else 'Sn25',
             'xrd_time':'initial','image_time':'0h','image_file':str(image_path.relative_to(ROOT)),
             'xrd_file':str(xrd_path.relative_to(ROOT)),
             'peak14_angle_deg':location,'peak14_apparent_fwhm_deg':width,
             'peak14_background_subtracted_height_cps':height,
             'peak14_net_area_13p4_to_14p4_cps_deg':float(np.trapezoid(net[window],x[window])),
             'peak24_angle_deg':peak(x,y,(23.7,24.8))[0],
             'peak28_angle_deg':peak(x,y,(27.8,28.6))[0]}
        for j,c in enumerate('RGB'):
            row['initial_image_mean_'+c]=float(pixels[:,j].mean())
            row['initial_image_spatial_sd_'+c]=float(pixels[:,j].std())
            row['separate_future_delta3h_'+c]=float(t['corrected_delta_'+c])
        row['separate_future_rgb_distance3h']=float(t['rgb_distance_of_means'])
        rows.append(row);data[tag]=(x,y,net,height,image,(mx,my,w-2*mx,h-2*my))
        for kind,path in [('xrd',xrd_path),('initial_image',image_path)]:
            manifest.append({'sample':tag,'kind':kind,'path':str(path.relative_to(ROOT)),
                             'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest.append({'kind':'future_image_metrics','path':str(temporal_path.relative_to(ROOT)),
                     'sha256':hashlib.sha256(temporal_path.read_bytes()).hexdigest()})
    with (OUT/'paired_training_example.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (OUT/'analysis_config.json').write_text(json.dumps({
        'mapping':'sample numbers previously confirmed by user',
        'angle_axis':'instrument header theta/2theta degrees; convention/source not confirmed',
        'smoothing':'5-point moving average',
        'peak_search':[13.4,14.4],'background_windows':[[13.0,13.3],[14.6,14.9]],
        'net_area_window':[13.4,14.4],'phase_assignment':None,
        'instrument_broadening_corrected':False,'image_outer_margin_each_edge':.18,
        'initial_images':'original uncorrected crops; initial features only',
        'future_metrics':'existing 05 analysis, 3h minus0h, ellipse included, stored separately',
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
    fig,axes=plt.subplots(2,3,figsize=(14,9),gridspec_kw={'width_ratios':[1,1,1.6]})
    for row_index,tags in enumerate((['BrRb_1','BrRb_2'],['Sn25_1','Sn25_2'])):
        for col,tag in enumerate(tags):
            x,y,net,height,image,box=data[tag]
            axes[row_index,col].imshow(image)
            axes[row_index,col].add_patch(plt.Rectangle(box[:2],box[2],box[3],fill=False,color='lime',lw=1))
            axes[row_index,col].set_title(tag+'：成膜直後の画像',fontproperties=font)
            axes[row_index,col].axis('off')
        ax=axes[row_index,2]
        for tag in tags:
            x,y,net,height,image,box=data[tag]
            record=next(r for r in rows if r['sample']==tag)
            ax.plot(x,net/height,label=f'{tag}: {record["peak14_angle_deg"]:.2f} deg / {record["peak14_apparent_fwhm_deg"]:.3f} deg')
        ax.axhline(.5,color='gray',ls=':');ax.set_xlim(13.3,14.6);ax.set_ylim(-.1,1.15)
        ax.set_title('同じ組成内でピークの形を比較',fontproperties=font)
        ax.set_xlabel('ファイル記載の角度（°）',fontproperties=font)
        ax.set_ylabel('局所背景を引き、ピーク高さを1に規格化',fontproperties=font)
        ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('練習① 同じ膜の「初期画像」と「初期XRD」を対応させる',fontproperties=font,fontsize=17)
    fig.text(.5,.01,'相の同定・良否判定ではありません。緑枠は画像特徴を測る範囲です。',ha='center',fontproperties=font)
    fig.tight_layout(rect=(0,.035,1,.95));save(fig,'01_同じ膜の画像とXRD')
    tag='Sn25_1';x,y,net,height,_,_=data[tag];r=next(r for r in rows if r['sample']==tag)
    peak_index=np.flatnonzero((x>=13.4)&(x<=14.4))[np.argmax(net[(x>=13.4)&(x<=14.4)])]
    left=peak_index;right=peak_index;half=height/2
    while net[left]>half:left-=1
    while net[right]>half:right+=1
    xl=float(np.interp(half,net[left:left+2],x[left:left+2]))
    xr=float(np.interp(half,net[right-1:right+1][::-1],x[right-1:right+1][::-1]))
    assert abs((xr-xl)-r['peak14_apparent_fwhm_deg'])<1e-9
    fig,ax=plt.subplots(figsize=(10,6))
    ax.plot(x,net,color='C0',label='Sn25_1');ax.set_xlim(13.2,14.6);ax.set_ylim(-height*.08,height*1.35)
    ax.axhline(0,color='gray',lw=.8);ax.hlines(half,xl,xr,color='C3',ls='--')
    ax.annotate('',xy=(xl,half),xytext=(xr,half),arrowprops={'arrowstyle':'<->','color':'C3'})
    ax.text((xl+xr)/2,half+height*.07,f'半値幅：約{xr-xl:.3f}°',ha='center',fontproperties=font,color='C3',fontsize=14)
    ax.annotate(f'ピーク位置：約{r["peak14_angle_deg"]:.2f}°',xy=(r['peak14_angle_deg'],height),
                xytext=(14.0,height*1.2),arrowprops={'arrowstyle':'->'},fontproperties=font,fontsize=13)
    ax.fill_between(x,net,where=(x>=13.4)&(x<=14.4),alpha=.12,color='C0')
    ax.set_title('練習② 位置・幅・面積を取り出す（相の名前はまだ付けない）',fontproperties=font,fontsize=15)
    ax.set_xlabel('ファイル記載の角度（°）',fontproperties=font)
    ax.set_ylabel('局所背景を差し引いた強度（cps）',fontproperties=font)
    ax.grid(alpha=.2);fig.tight_layout();save(fig,'02_ピークの読み方')
    report(rows)
    print(OUT)


def report(rows):
    lines=['# 10月15日のデータで、画像とXRDを対応させる練習','',
           '**まず [画像とXRDを並べた図](01_同じ膜の画像とXRD.png)、次に [ピークの読み方](02_ピークの読み方.png) を見てください。**','',
           '## 今回の練習の目的','',
           '同じ膜の初期画像から特徴量を出し、同じ膜の初期XRDから取り出した数値と1行にまとめる、という手順を実データで行いました。良い膜／悪い膜を判定したり、機械学習を学習させたりはしていません。','',
           '## ① 同じ膜を対応させる','',
           'BrRb_1・BrRb_2・Sn25_1・Sn25_2の4膜。画像番号とXRD番号の対応は以前ユーザー確認済みです。XRDは成膜直後のみなので、ここでは画像も0hを使っています。','',
           '## ② XRDで読むのはこの3つ','',
           '- **ピーク位置**：山の頂点がある角度。まずはファイルに記録された角度を読みます。',
           '- **見かけの半値幅**：局所背景を引いた山の高さが半分になるところで測った横幅。細い＝良い膜とは決めません。',
           '- **ピーク面積**：決めた角度範囲の背景差引き後の信号を積分した値。今回は13.4〜14.4°。単位はcps・度で、相の含有率ではありません。','',
           '| 膜 | 約14°の位置 | 見かけの半値幅 | 背景差引きピーク高さ | 13.4〜14.4°の面積 |',
           '|---|---:|---:|---:|---:|']
    for r in rows:lines.append(f'| {r["sample"]} | {r["peak14_angle_deg"]:.2f}° | {r["peak14_apparent_fwhm_deg"]:.3f}° | {r["peak14_background_subtracted_height_cps"]:.1f} cps | {r["peak14_net_area_13p4_to_14p4_cps_deg"]:.1f} |')
    lines+=['','## ③ 画像から出した数値と、同じ行へ並べる','',
            '0hの元切り抜き画像から、各辺18%を除く中央領域の平均RGB・画素標準偏差を計算しました。古い撮影環境で、背景・反射・自動設定の影響が残ります。画像特徴を材料固有の色や良否とは扱いません。','',
            '| 膜 | 初期の平均R / G / B | 初期の色むらSD R / G / B |','|---|---|---|']
    for r in rows:lines.append('| '+r['sample']+' | '+' / '.join(f'{r["initial_image_mean_"+c]:.2f}' for c in 'RGB')+' | '+' / '.join(f'{r["initial_image_spatial_sd_"+c]:.2f}' for c in 'RGB')+' |')
    lines+=['','例えばSn25_1の1行に「画像の平均色・色むら」と「XRDの位置13.84°・見かけ幅0.361°」が並びます。これを別々に作製した膜について増やすと、画像でXRD特徴を推定できるか検証するための表になります。','',
            '## この4膜で考えられること','',
            '- まず同組成の2膜ずつを見ます。BrRb同士の半値幅は約0.302／0.295°、Sn25同士は約0.361／0.351°です。小さな差の有意性は評価していません。',
            '- 組成が違う2群を混ぜて「暗いほど半値幅が小さい」などの法則は作れません。組成が画像とXRDの両方に影響し得ます。',
            '- 特定の相がある／ない、という教師ラベルを作るには、X線源・基板・測定条件と参照パターンでピーク帰属を確認する必要があります。今は数値を対応させる練習までです。','',
            '## 初期XRDと、その後の変化は別の問い','',
            '初期画像で初期XRDを推定する問いと、初期XRDから後の変色を予測する問いは別です。参考として、既存の最新画像解析（05フォルダ・楕円を含む）から0→3hのRGB変化を同じCSVに別の列で追加しました。','',
            '| 膜 | 0→3h ΔR / ΔG / ΔB |','|---|---|']
    for r in rows:lines.append('| '+r['sample']+' | '+' / '.join(f'{r["separate_future_delta3h_"+c]:+.2f}' for c in 'RGB')+' |')
    lines+=['','BrRbの2膜は約14°の見かけ幅が近い一方、3hの色変化には差があります。この4膜から「ピークが細ければ変色しにくい」という単純なルールは支持できません。初期XRDだけで、その後の相変化やPbI2生成を確認することもできません。','',
            '## 次に今回の5min・10minへ適用するとき','',
            '1. 各膜のXRDのファイルと測定時点を確認する。',
            '2. 同じ試料ID・対応する撮影時点の画像と結び付ける。',
            '3. 同じ手順で数値を出す。ただしピークの探索範囲や帰属は組成・測定条件に合わせて確認する。',
            '4. 最初は画像特徴とXRD特徴を並べて違いを見て、根拠のある評価を決めてからデータを増やす。','',
            '## 数値と方法の注意','',
            '- [対応表CSV](paired_training_example.csv)は4行。膜の品質ラベルは付けていません。将来の変化の列にはseparate_futureという名前を付け、初期情報と区別しました。',
            '- 元データ各5701点、角度3〜60°、0.01°刻み。5点移動平均、13.0〜13.3°と14.6〜14.9°の中央値を直線で結ぶ局所背景を使用。以前の03フォルダと同じピーク抽出方法です。',
            '- 元の角度見出しは「θ/2θ, °」。X線源・軸の規約・基板・測定条件は未確認です。約14°などの山に結晶相名を勝手に付けていません。',
            '- 半値幅はプロファイルフィットや装置幅補正をしていない見かけの値。結晶子径・結晶性の点数には変換していません。',
            '- 強度・面積は配向・膜厚・測定条件等にも依存するため、相の割合や良否として読み替えません。',
            '- n=4、同組成は各2膜。相関係数、回帰線、機械学習の精度評価は行いません。',
            '- 以前の03フォルダのRGB値は初期の画像解析版です。今回の未来の変化の列は05フォルダの値なので、過去の表と僅かに異なります。初期画像の指標は0hの元切り抜き画像から今回計算した値です。',
            '- 既存の解析結果・元データは上書きしていません。ファイルとSHA-256はinput_manifest.json、解析条件はanalysis_config.json。','',
            '再実行：`python3 notebooks/film_time_series/xrd_image_practice.py`。NumPy、Pillow、Matplotlibが必要です。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
