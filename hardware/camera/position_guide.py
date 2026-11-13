"""Position guide geometry in full-resolution image coordinates."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path


def validate_guide(profile, context):
    if profile.get('schema_version') != 1 or profile.get('context') != context:
        raise ValueError('位置枠の機器・解像度が一致しません')
    points=profile.get('corners_normalized',[])
    if len(points)!=4:raise ValueError('四隅を4点指定してください')
    for point in points:
        if not isinstance(point,(list,tuple)) or len(point)!=2 or any(
            isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
            or not 0<=v<=1 for v in point):
            raise ValueError('枠が画像の範囲外です')
    turns=[]
    for i in range(4):
        a,b,c=points[i],points[(i+1)%4],points[(i+2)%4]
        turns.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
    if any(t<=1e-8 for t in turns):
        raise ValueError('左上→右上→右下→左下の順に指定してください')
    area=sum(points[i][0]*points[(i+1)%4][1]-points[(i+1)%4][0]*points[i][1] for i in range(4))/2
    if area<1e-5:raise ValueError('枠が小さすぎます')
    if points[0][1]+points[1][1] >= points[2][1]+points[3][1]:
        raise ValueError('上側の2点から指定してください')
    return [[float(x),float(y)] for x,y in points]


def make_guide(points,context,source):
    profile={'schema_version':1,'context':context,'corners_normalized':points,
             'created_at':datetime.now().astimezone().isoformat(),'source':source,
             'meaning':'substrate outline, not the color-analysis ROI',
             'orientation_note':'UP is screen orientation; substrate identity/orientation is not detected'}
    validate_guide(profile,context)
    return profile


def load_guide(path,context):
    profile=json.loads(Path(path).read_text());validate_guide(profile,context)
    return profile


def guide_record(profile,registered):
    if profile is None:return {'state':'none','alignment_verified':False}
    digest=hashlib.sha256(json.dumps(profile,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'state':'registered' if registered else 'candidate_unregistered',
            'profile_sha256':digest,'profile':profile,'alignment_verified':False,
            'note':'Visual guide only; no automatic position/height/tilt verification'}


def translate_corners(points,dx_pixels,dy_pixels,size):
    """Clamp the WHOLE polygon's translation, preserving its shape and size."""
    w,h=size
    if w<=1 or h<=1 or not all(math.isfinite(v) for v in (dx_pixels,dy_pixels)):
        raise ValueError('Invalid translation')
    dx=dx_pixels/(w-1);dy=dy_pixels/(h-1)
    dx=max(-min(p[0] for p in points),min(dx,1-max(p[0] for p in points)))
    dy=max(-min(p[1] for p in points),min(dy,1-max(p[1] for p in points)))
    return [[x+dx,y+dy] for x,y in points],(dx*(w-1),dy*(h-1))


def viewport(size,points,zoom):
    w,h=size
    if not zoom or not points:return (0,0,w,h)
    xs=[p[0]*(w-1) for p in points];ys=[p[1]*(h-1) for p in points]
    width=min(w,max(320,round((max(xs)-min(xs))*2.2)))
    height=min(h,max(240,round((max(ys)-min(ys))*2.2)))
    x=max(0,min(w-width,round((min(xs)+max(xs)-width)/2)))
    y=max(0,min(h-height,round((min(ys)+max(ys)-height)/2)))
    return (x,y,x+width,y+height)


def display_mapping(size,widget_size,view):
    left,top,right,bottom=view
    scale=min(widget_size[0]/(right-left),widget_size[1]/(bottom-top))
    dw,dh=max(1,int((right-left)*scale)),max(1,int((bottom-top)*scale))
    return {'size':size,'view':view,'display_size':(dw,dh),
            'offset':((widget_size[0]-dw)/2,(widget_size[1]-dh)/2)}


def normalized_to_display(point,mapping):
    w,h=mapping['size'];left,top,right,bottom=mapping['view'];dw,dh=mapping['display_size']
    return ((point[0]*(w-1)-left)*dw/(right-left),
            (point[1]*(h-1)-top)*dh/(bottom-top))


def widget_to_normalized(point,mapping):
    x,y=point;ox,oy=mapping['offset'];dw,dh=mapping['display_size']
    if not (ox<=x<ox+dw and oy<=y<oy+dh):return None
    w,h=mapping['size'];left,top,right,bottom=mapping['view']
    px=left+(x-ox)*(right-left)/dw;py=top+(y-oy)*(bottom-top)/dh
    return [min(1,max(0,px/(w-1))),min(1,max(0,py/(h-1)))]


def overlay_preview(image,profile,mapping,editing_points=()):
    """Draw on a COPY of the preview; never alter the sensor frame or JPEG."""
    from PIL import ImageDraw
    preview=image.copy();draw=ImageDraw.Draw(preview)
    if profile:
        points=[normalized_to_display(p,mapping) for p in profile['corners_normalized']]
        draw.line(points+[points[0]],fill='black',width=5)
        draw.line(points+[points[0]],fill='white',width=2)
        cx=sum(x for x,y in points)/4;cy=sum(y for x,y in points)/4
        draw.line((cx-7,cy,cx+7,cy),fill='white',width=1)
        draw.line((cx,cy-7,cx,cy+7),fill='white',width=1)
        tx=(points[0][0]+points[1][0])/2;ty=(points[0][1]+points[1][1])/2
        draw.text((tx-8,max(0,ty-15)),'UP',fill='white',stroke_width=1,stroke_fill='black')
    for i,p in enumerate(editing_points):
        x,y=normalized_to_display(p,mapping)
        draw.ellipse((x-4,y-4,x+4,y+4),fill='yellow',outline='black')
        draw.text((x+5,y),str(i+1),fill='yellow',stroke_width=1,stroke_fill='black')
    return preview
