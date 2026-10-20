"""Make color maps with no ellipse exclusion, keeping the 18% outer margin.
Reuse saved full-precision differences and registration; do not re-estimate color.
"""
import csv,json
import numpy as np
from PIL import Image
from aligned_color_analysis import OUT,TAGS,mask_for,save,plt,cv2

def main():
 sensitivity=list(csv.DictReader((OUT/'roi_sensitivity.csv').open(encoding='utf-8-sig')))
 regs=json.loads((OUT/'registration.json').read_text())
 for tag in TAGS:
  dest=OUT/tag
  images=[np.asarray(Image.open(dest/f'{t}h_aligned_corrected.png')) for t in range(4)]
  h,w=images[0].shape[:2];valids=[]
  for t in range(4):
   r=next(r for r in regs if r['sample']==tag and r['hour']==t)
   if t==0:v=np.ones((h,w),bool)
   else:
    warp=np.array(r['warp_reference_to_resized_input'],np.float32)
    v=cv2.warpAffine(np.ones((h,w),np.uint8),warp,(w,h),flags=cv2.INTER_NEAREST|cv2.WARP_INVERSE_MAP)>0
    v=cv2.erode(v.astype(np.uint8),np.ones((5,5),np.uint8))>0
   valids.append(v)
  mask=mask_for(h,w,.18,np.logical_and.reduce(valids),tag,exclude=False)
  Image.fromarray((mask*255).astype(np.uint8)).save(dest/'analysis_mask_with_ellipse.png')
  data=[np.load(dest/f'{t}h_color_difference.npz') for t in range(4)]
  # Cross-check that no excluded-region values were lost in stored numerical maps.
  for t,v in enumerate(data):
   row=next(r for r in sensitivity if r['sample']==tag and int(r['hour'])==t and r['margin_fraction']=='0.18' and r['reflection_excluded']=='False')
   assert mask.sum()==int(row['pixels'])
   for j,ch in enumerate('RGB'):
    assert np.isclose(v['delta_rgb'][mask,j].mean(),float(row['delta_'+ch]),atol=1e-4)
   np.savez_compressed(dest/f'{t}h_color_difference_with_ellipse.npz',delta_rgb=v['delta_rgb'],rgb_distance=v['rgb_distance'],analysis_mask=mask)
  fig,axs=plt.subplots(3,4,figsize=(12,8.8),layout='constrained')
  for t,v in enumerate(data):
   axs[0,t].imshow(images[t]);axs[0,t].contour(mask,levels=[.5],colors=['lime'],linewidths=.8);axs[0,t].set_title(f'{tag}: {t} h, corrected')
   low=next(r for r in regs if r['sample']==tag and r['hour']==t)['low_alignment_confidence']
   im=axs[1,t].imshow(np.ma.array(v['rgb_distance'],mask=~mask),cmap='magma',vmin=0,vmax=50)
   axs[1,t].set_title('RGB distance from 0 h'+(' [LOW ALIGNMENT]' if low else ''),fontsize=9)
   imr=axs[2,t].imshow(np.ma.array(v['delta_rgb'][:,:,0],mask=~mask),cmap='coolwarm',vmin=-30,vmax=30)
   axs[2,t].set_title('Signed red change from 0 h')
   for ax in axs[:,t]:ax.axis('off')
  fig.colorbar(im,ax=list(axs[1]),shrink=.6,label='JPEG RGB distance (fixed 0–50)')
  fig.colorbar(imr,ax=list(axs[2]),shrink=.6,label='JPEG R units (fixed -30 to 30)')
  fig.suptitle('Ellipse INCLUDED: central region only (18% outer margin); not the entire film',fontsize=11)
  save(fig,dest/'color_change_maps_with_ellipse')
 print('Created 4 no-ellipse-exclusion maps (PNG/PDF); masks and RGB means match existing CSV.')
if __name__=='__main__':main()
