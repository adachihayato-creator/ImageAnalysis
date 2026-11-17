"""Refresh date-based navigation; results are stored directly, not copied elsewhere."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results'
DESCRIPTIONS={'20260717':'7月の切り抜き画像・XRD対応資料','20261015':'4膜の経時画像・背景補正・初期XRD','20261110':'撮影の再現性と固定設定','20261111':'白枠・置き直し再現性と5分/10分比較','20261112':'Sn10%の経時画像・XRDと撮影ばらつき','20261113':'斑点・区画解析・1日後の画像とXRD','20261117':'今日の撮影整理・XRD対応・予測試作'}
entries=[]
for date in sorted(p for p in OUT.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name)==8):
 parts=[f'# {date.name}の結果一覧','',DESCRIPTIONS.get(date.name,''),'']
 for folder in sorted(p for p in date.iterdir() if p.is_dir()):
  guide=folder/'README.md';target=str(guide.relative_to(date)) if guide.exists() else folder.name+'/';parts.append(f'- [{folder.name}]({target})')
 (date/'INDEX.md').write_text('\n'.join(parts)+'\n');entries.append(f'- [{date.name}]({date.name}/INDEX.md)：{DESCRIPTIONS.get(date.name,"")}')
(OUT/'README.md').write_text('# 研究結果（日付別）\n\n解析結果の保存先をresultsへ統一しました。日付を選び、各解析の図・CSV・説明を開いてください。\n\n'+'\n'.join(entries)+'\n\n## 保存場所\n\n- data/raw：原画像・撮影JSON・XRD原本と試料条件。\n- results/YYYYMMDD：解析結果、検証、切り抜き・補正画像、予測、数値CSV。\n- notebooks：解析コード。\n\n各日の00_主要結果は主要図の閲覧用コピーです。詳細は同日内の各解析フォルダに保存しています。旧data/processedの全ファイルは移行・照合済みで、旧フォルダは削除しました。記録：data/results_migration_20261117.json。\n\n今回のXRD予測：[20261117/06_xrd_ratio_prediction/README.md](20261117/06_xrd_ratio_prediction/README.md)。\n\n一覧更新：python3 scripts/collect_results.py。\n')
print('Updated',len(entries),'date indexes')
