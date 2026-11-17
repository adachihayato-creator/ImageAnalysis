"""Resolve measurement pairs by numeric inventory, preserve original names and timing gaps."""
from pathlib import Path
from datetime import datetime
import csv,json,hashlib,shutil,re
ROOT=Path(__file__).resolve().parents[2]
B=ROOT/'data/raw/XRD/20261117';inv=list(csv.DictReader((B/'scan_inventory.csv').open(encoding='utf-8-sig')))
meta_paths={
 ('Tuji','plain'):ROOT/'data/raw/Tuji/FACsPbI3_FA85Cs15/20261117/condition_metadata.json',
 ('Tuji','RbBr'):ROOT/'data/raw/Tuji/FACsPbI3_FA85Cs15_BrRb20percent/20261117/condition_metadata.json',
 ('Touma','plain'):ROOT/'data/raw/Touma/FACsPbI3_FA85Cs15/20261117_130C_10min/condition_metadata.json',
 ('Touma','Sn10'):ROOT/'data/raw/Touma/FACsSnPbI3_FA85Cs15_Sn10/20261117_130C_10min/condition_metadata.json'}
metas={k:json.loads(p.read_text()) for k,p in meta_paths.items()};groups={}
for r in inv:
 name=Path(r['rasx']).stem;own=r['owner']
 if own=='Tuji':
  if name.startswith('BrRb'):family='RbBr';i=int(re.search(r'20% (\d)',name)[1])
  else:
   m=re.search(r'FACsPbI3 (50|90) (\d)',name);family='plain';i=int(m[2])+(2 if m[1]=='50' else 0)
 else:
  family='Sn10' if name.startswith('SnF2') else 'plain';i=int(re.search(r'(?:SnF2 10|FACsPbI3) (\d)',name)[1])
 groups.setdefault((own,family,i),[]).append(r)
plan=[];records=[]
for (own,family,i),scans in groups.items():
 scans.sort(key=lambda r:r['StartTime_minus_6m30s_JST']);sample=metas[own,family]['samples'][i-1];meta=meta_paths[own,family];photoobs=[{'elapsed_age':'0h','image':sample['image'],'camera_json':sample['camera_json']}]+sample.get('time_series',[])
 photoobs=[dict(ob) for ob in photoobs]
 for ob in photoobs:ob['_time']=datetime.fromisoformat(json.loads((ROOT/ob['camera_json']).read_text())['captured_at'])
 sample['xrd_measurements']=[]
 for index,r in enumerate(scans,1):
  ras=ROOT/r['rasx'];txt=ROOT/r['matched_txt_by_numeric_data'];stem=ras.stem;match=re.search(r' ([0-9.]+h)$',stem);label=match[1] if match else '0h';conflict=own=='Touma' and family=='plain' and i==1 and index==3
  stage=f'measurement_{index:02d}_'+('3h_or_3.5h' if conflict else label)
  dest=meta.parent/f'film_{i:02d}'/'XRD'/stage
  for src in [ras,txt]:
   target=dest/src.name
   if not src.exists() and target.exists():src_for_hash=target
   elif src.exists() and not target.exists():src_for_hash=src
   else:raise RuntimeError('Unsafe move '+str(src))
   plan.append({'source':str(src.relative_to(ROOT)),'destination':str(target.relative_to(ROOT)),'sha256':hashlib.sha256(src_for_hash.read_bytes()).hexdigest()})
  end=datetime.fromisoformat(r['EndTime_minus_6m30s_JST']);start=datetime.fromisoformat(r['StartTime_minus_6m30s_JST']);nearest=min(photoobs,key=lambda ob:abs((ob['_time']-end).total_seconds()));following=[ob for ob in photoobs if ob['_time']>=end];after=min(following,key=lambda ob:ob['_time']) if following else None
  initial_start=datetime.fromisoformat(scans[0]['StartTime_minus_6m30s_JST']);row={'owner':own,'family':family,'film_number':i,'sample_id':sample.get('sample_id',sample.get('provisional_sample_id')),'measurement_order':index,'nominal_xrd_label':'3h_or_3.5h_unresolved' if conflict else label,'label_basis':'User confirmed initial0h and filename ages; contradictory3h/3.5h not resolvable without deposition time' if conflict else 'RASX label and corrected chronological measurement order; user confirmed0h meaning','rasx':str((dest/ras.name).relative_to(ROOT)),'txt':str((dest/txt.name).relative_to(ROOT)),'txt_rasx_numeric_pair_verified':True,'original_filename_mismatch':r['filename_stems_match']=='False','corrected_start_JST':start.isoformat(),'corrected_end_JST':end.isoformat(),'minutes_since_initial_xrd_start':(start-initial_start).total_seconds()/60,'nearest_photo':nearest['image'],'nearest_photo_age':nearest['elapsed_age'],'photo_minus_xrd_end_minutes':(nearest['_time']-end).total_seconds()/60,'first_photo_after_xrd':after['image'] if after else None,'first_photo_after_xrd_age':after['elapsed_age'] if after else None,'first_photo_after_xrd_gap_minutes':(after['_time']-end).total_seconds()/60 if after else None,'pairing_status':'Time candidates only; not assumed simultaneous or auto-approved training pair'}
  records.append(row);sample['xrd_measurements'].append({k:v for k,v in row.items() if k not in ['owner','family','film_number','sample_id']})
# Preflight all paths, then move byte-preserving originals.
log=B/'organized_measurements_manifest.json';log.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
for r in plan:
 src=ROOT/r['source'];dest=ROOT/r['destination'];dest.parent.mkdir(parents=True,exist_ok=True);
 if src.exists():shutil.move(str(src),str(dest))
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==r['sha256']
for k,p in meta_paths.items():
 metas[k]['xrd_clock_correction_seconds']=-390;metas[k]['xrd_pairing_note']='Numeric TXT/RASX pairing, corrected chronological order, photos are time candidates with explicit gaps, not simultaneous.';p.write_text(json.dumps(metas[k],ensure_ascii=False,indent=2)+'\n')
O=ROOT/'results/20261117/05_xrd_image_time_matching';O.mkdir(parents=True,exist_ok=True)
with (O/'measurement_photo_timing.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
(O/'measurement_photo_timing.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
(O/'README.md').write_text('# XRDと画像の対応整理\n\n28測定を10膜へ対応付け。ユーザー確認済みの膜番号で整理。元ファイル名は維持し、TXT/RASXの数値全点一致に基づいてペアリング。XRD時刻から390秒を引いた開始/終了時刻を使用。\n\nSn10・膜2は初回RASXと1h名のTXT、1hRASXと無時点名のTXTを同じ測定として保存。時間順でも確認。Touma Snなし膜1の最後はRASX3h/TXT3.5hの名称不一致が残るためmeasurement_03_3h_or_3.5hへ保存。初回XRD開始から約196分だが、初回開始が正確な成膜終了時刻ではないため3h/3.5hを時刻だけで断定しない。\n\n対応表には同じ膜の最も近い画像（時差の正負あり）と、測定終了後の最初の画像を別々に記載。同じ公称時間だけで紐付けず、同時測定ともみなさない。画像が前の場合は測定前候補として明示。後続画像がなければ空欄。候補は自動的に機械学習用の正解ペアとして確定しない。\n')
with (B/'README.md').open('a') as f:f.write('\n## 試料別への整理完了\n\n原本56ファイルは各試料のfilm_番号/XRD/measurement_番号_時点へ移動。移動先とSHA256はorganized_measurements_manifest.json。scan_inventory.csvのパスは最初の取込時点の履歴。現在のパスと撮影候補はresults/20261117/05_xrd_image_time_matching/measurement_photo_timing.csv。\n')
for folder in [B/'Touma/261117',B/'Tuji/261117',B/'Touma',B/'Tuji']:
 if folder.exists() and not any(folder.iterdir()):folder.rmdir()
print('Organized',len(plan),'files,',len(records),'measurements,',len(groups),'films')
for r in records:
 if r['original_filename_mismatch']:print(r['family'],r['film_number'],r['nominal_xrd_label'],r['corrected_start_JST'],r['corrected_end_JST'])
print('Post-measurement photo candidates:',sum(r['first_photo_after_xrd'] is not None for r in records),'no later photo:',sum(r['first_photo_after_xrd'] is None for r in records))
