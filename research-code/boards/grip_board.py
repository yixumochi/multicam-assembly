from math import atan2, cos, degrees, hypot, radians, sin
import hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen import canvas
from grip_geometry import D, UPPER, LOWER, REF, TIMBER, approx, angle, read
from grip_inspect import SOURCE
from machine_board import tint
import render_boards as b

RED=b.HexColor('#CF3838')
RED_RGB='#D92E39'
PAGES=('Timber carried by the left gripper','Timber held by the right gripper')
DETAIL=(
 {437:(109,163,383,317.125),538:(155,178,440,338.3125),639:(193,216,487,381.375)},
 {n:(324,218,612,380) for n in (437,538,639)})

def proj(p,box,x,y,w,h):
    return (x+(p[0]-box[0])*w/(box[2]-box[0]), y+(p[1]-box[1])*h/(box[3]-box[1]))

def endpoint(mask,line):
    x,y=line[2:]
    dx,dy=x-line[0],y-line[1]
    dist=hypot(dx,dy)
    for step in range(19):
        ex,ey=x+step*.5*dx/dist,y+step*.5*dy/dist
        if mask.getpixel((round(ex),round(ey))):
            return ex,ey
    raise ValueError(f'Jaw-to-timber interface not found near {x}, {y}')

def red_arrow(draw,tail,tip,stroke):
    x,y=tail
    dx,dy=tip[0]-x,tip[1]-y
    length=hypot(dx,dy)
    ux,uy=dx/length,dy/length
    def point(d,s=0):
        return x+d*ux-s*uy,y+d*uy+s*ux
    spacing=4.4*stroke
    for j in range(int(length/spacing)+1):
        start=j*spacing
        end=min(start+spacing*.59,length)
        if end>start:
            seg=[point(start),point(end)]
            draw.line(seg,fill='white',width=stroke+3)
            draw.line(seg,fill=RED_RGB,width=stroke)
    wings=[point(length-4*stroke,2.1*stroke),tip,point(length-4*stroke,-2.1*stroke)]
    draw.line(wings,fill='white',width=stroke+3,joint='curve')
    draw.line(wings,fill=RED_RGB,width=stroke,joint='curve')

def detail_image(i,f,box,w,h,color):
    im=Image.open(f.photo).convert('RGB')
    masked=tint(im,f.mask,color)
    crop=masked.transform((w,h),Image.Transform.EXTENT,box,Image.Resampling.BICUBIC)
    d=ImageDraw.Draw(crop)
    for line in (UPPER[i][f.number],LOWER[i][f.number]):
        p=proj(line[:2],box,0,0,w,h)
        q=proj(endpoint(f.mask,line),box,0,0,w,h)
        red_arrow(d,p,q,max(3,round(w/140)))
    return crop

def grip_detail_frames(c,i,fs):
    tw=(b.COL_W-20)/3
    th=tw*9/16
    for x,title,lower in ((b.MARGIN,'Three source frames','Masks of the held timber'),
                          (b.RIGHT,'Grip on the timber','Upper jaw and timber edge')):
        b.txt(c,title,x,169,12,bold=True)
        b.txt(c,lower,x,312,12,bold=True)
    for j,(f,color) in enumerate(zip(fs,b.COLORS)):
        n=f.number
        lx=b.MARGIN+j*(tw+10)
        rx=b.RIGHT+j*(tw+10)
        im=Image.open(f.photo).convert('RGB')
        whole=(0,0,*f.size)
        b.picture(c,im,lx,180,tw,th)
        line=REF[n]
        ref1,ref2=[proj(pt,whole,lx,180,tw,th) for pt in (line[:2],line[2:])]
        b.segment(c,ref1,ref2,b.WHITE,2.2)
        b.segment(c,ref1,ref2,b.REF,1.25)
        b.circle(c,proj(f.traced('point'),whole,lx,180,tw,th),2.6,b.REF,b.WHITE,1)
        box=DETAIL[i][n]
        b.picture(c,detail_image(i,f,box,720,405,color),rx,180,tw,th)
        b.rect(c,lx,324,tw,th,fill=b.CARD)
        b.picture(c,b.colored_mask(f.mask,color,.78),lx,324,tw,th)
        # The second right-hand row records observed geometry without force arrows.
        jaw=UPPER[i][n]
        px,py=jaw[2:]
        zoom=(px-51,py-33.75,px+69,py+33.75)
        z=im.transform((640,360),Image.Transform.EXTENT,zoom,Image.Resampling.BICUBIC)
        b.picture(c,z,rx,324,tw,th)
        c.saveState()
        clip=c.beginPath()
        clip.rect(rx,b.PAGE_H-324-th,tw,th)
        c.clipPath(clip,stroke=0)
        for geometry,linecolor in ((TIMBER[i][n],color),(jaw,b.INK)):
            p,q=[proj(pt,zoom,rx,324,tw,th) for pt in (geometry[:2],geometry[2:])]
            b.segment(c,p,q,b.WHITE,3.2);b.segment(c,p,q,linecolor,1.45)
        c.restoreState()
        for x in (lx,rx):
            b.segment(c,(x,292),(x+14,292),color,2.2)
            b.txt(c,f'{f.role.capitalize()}  {f.time_label}',x+18,296,9.5,bold=True)

def quantities(c,i,fs):
    x,y=b.RIGHT,533
    b.txt(c,'On-screen angle, tool against the member edge',x,520,13,bold=True)
    b.rect(c,x,y,b.COL_W,203,fill=b.CARD,radius=5)
    ox,oy=x+32,y+149
    def polar(d,rad):
        return ox+rad*cos(radians(d)),oy-rad*sin(radians(d))
    for guide in (30,60,90):
        b.segment(c,(ox,oy),polar(guide,111))
        gx,gy=polar(guide,119)
        b.aligned(c,f'{guide}°',gx,gy,8,b.MUTED,.5)
    b.path_line(c,[polar(v,111) for v in range(91)],b.LINE,.8)
    b.segment(c,(ox,oy),polar(0,117),b.REF,1.6)
    b.circle(c,(ox,oy),2.7,b.REF)
    b.txt(c,'Upright edge  0°',ox,oy+17,8,b.MUTED)
    tx=x+166
    b.segment(c,(tx-9,y+17),(tx-9,y+185))
    columns=[tx,tx+71,tx+153,tx+237]
    for cx,word in zip(columns,['Frame','Timber edge','Upper jaw','Joint feed']):
        b.txt(c,word,cx,y+25,9.1,bold=True)
    for j,(f,color) in enumerate(zip(fs,b.COLORS)):
        n=f.number
        by=y+58+j*43
        for ln,offset in ((TIMBER[i][n],0),(UPPER[i][n],28)):
            ang=angle(ln,REF[n])
            b.segment(c,polar(ang,47+offset+j*3),polar(ang,70+offset+j*3),b.INK,3.2)
            b.segment(c,polar(ang,47+offset+j*3),polar(ang,70+offset+j*3),color,1.65)
        b.segment(c,(tx,by-3),(tx+9,by-3),color,2)
        b.txt(c,f.time_label,tx+13,by,9,bold=True)
        b.txt(c,f'about {approx(TIMBER[i][n],REF[n])}°',columns[1],by,9.5)
        b.txt(c,f'about {approx(UPPER[i][n],REF[n])}°',columns[2],by,9.5)
        b.txt(c,'Not readable' if i==0 else 'No feed seen',columns[3],by,9,b.MUTED)
        b.segment(c,(tx,by+13),(x+b.COL_W-12,by+13))
    b.text_block(c,'Angles are smaller projected angles to the fixed front upright.',tx,y+179,b.COL_W-180,8.3,2)

def extent(c,i,e,a,fs):
    x=b.MARGIN
    b.txt(c,'Common point',x,454,11,b.REF,True)
    b.txt(c,'Foot of the fixed front upright, at the sill.',x+95,454,9,b.MUTED)
    b.txt(c,'Masked member   '+PAGES[i],x,477,10.5,b.INK,True)
    b.text_block(c,e['description'],x,494,b.COL_W,8.6,2)
    b.txt(c,'Three aligned timber masks and their extent',x,520,13,bold=True)
    b.rect(c,x,533,b.COL_W,203,fill=b.CARD,radius=5)
    over,ref,bounds=b.registered_overlay(fs)
    l,t,r,bot=bounds
    box=tuple(map(int,(min(l,ref[0])-10,min(t,ref[1])-10,max(r,ref[0])+11,max(bot,ref[1])+11)))
    patch=over.crop(box)
    scale=min(240/patch.width,147/patch.height)
    w,h=patch.width*scale,patch.height*scale
    xx,yy=x+(.47*b.COL_W-w)/2,546+(147-h)/2
    b.picture(c,patch,xx,yy,w,h)
    p,q=proj((l,t),box,xx,yy,w,h),proj((r,bot),box,xx,yy,w,h)
    for u,v in ((p,(q[0],p[1])),((q[0],p[1]),q),(q,(p[0],q[1])),((p[0],q[1]),p)):
        b.segment(c,u,v,b.MUTED,.7,(3,2))
    b.circle(c,proj(ref,box,xx,yy,w,h),2.6,b.REF)
    bx=x+b.COL_W*.51
    b.txt(c,f'W {r-l} px     H {bot-t} px',bx,566,11,bold=True)
    note=('The lower end moves down and right as the timber rotates. The upper joint is partly obscured at the end.'
          if i==0 else 'The three silhouettes nearly coincide. The right gripper keeps holding this timber while the left robot approaches.')
    b.text_block(c,note,bx,594,b.COL_W*.45,10,5)
    b.text_block(c,'Masks translated to the middle-frame point. Extent in the original 960 × 540 frame.',x+12,722,b.COL_W-22,8.5,1)
    b.text_block(c,('Mask limited to the visible diagonal timber.' if i==0 else
                     'Above the crossing, the held timber is occluded by the front upright.'),x,752,b.COL_W,9,2)

def legend_and_notes(c,i):
    x=b.RIGHT
    b.txt(c,'Solid lines trace the visible timber edge and upper jaw.',x,445,9,b.MUTED)
    b.segment(c,(x,466),(x+18,466),RED,1.7,(4,2))
    b.segment(c,(x+18,466),(x+13,463),RED,1.4);b.segment(c,(x+18,466),(x+13,469),RED,1.4)
    b.txt(c,'Possible jaw-on-timber compression, drawn along the visible crosspieces.',x+25,469,9,RED,True)
    b.txt(c,'The arrows end at the visible interfaces. Their lengths carry no force scale.',x,490,9,b.MUTED)
    s=('Grip at the jaws is visible. The feed direction under load at the upper joint is unresolved.'
       if i==0 else 'The right timber is being held. No insertion by this gripper is visible in the interval.')
    b.text_block(c,s,x,752,b.COL_W,9,2)

def build(c,i,e,a,fs):
    x=b.MARGIN
    b.txt(c,'MULTICAM  /  V04 GRIP AND LOAD',x,32,11,b.MUTED,True)
    b.aligned(c,'TWO-EVENT REVIEW',b.PAGE_W-x,32,10,b.MUTED,1,True)
    b.txt(c,f'0{i+4}   '+PAGES[i],x,68,25,bold=True)
    b.txt(c,f"{e['label']}   ·   {e['start']:.2f}–{e['end']:.2f} s",x,94,12,b.MUTED)
    b.aligned(c,f"{e['id']}   ·   task29.mp4   ·   25 fps",b.PAGE_W-x,94,10,b.MUTED,1)
    b.segment(c,(x,112),(b.PAGE_W-x,112))
    b.txt(c,'01   Relative position and extent',x,140,16,bold=True)
    b.txt(c,'02   Change in angle and grip loading',b.RIGHT,140,16,bold=True)
    b.segment(c,(b.RIGHT-b.GAP/2,128),(b.RIGHT-b.GAP/2,776))
    grip_detail_frames(c,i,fs)
    extent(c,i,e,a,fs)
    legend_and_notes(c,i)
    quantities(c,i,fs)
    b.segment(c,(x,778),(b.PAGE_W-x,778))
    b.txt(c,'Source  task29.mp4, frames 000437 / 000538 / 000639, 960 × 540 px.',x,798,9,b.MUTED)
    b.txt(c,'Edge angles are rounded to 5°. The force magnitude and the three-dimensional contact-force vector are unmeasured.',x,814,9,b.MUTED)
    b.aligned(c,f'Review {i+1} / 2',b.PAGE_W-x,814,9,b.MUTED,1)
    c.showPage()

def preview(samples):
    w,h=1240,541
    im=Image.new('RGB',(w,h),'#F5F8FA')
    d=ImageDraw.Draw(im)
    def font(s,bold=False):
        return ImageFont.truetype(b.font_path(bold), s)
    d.text((24,16),'How two timber members are held in one frame',font=font(31,True),fill='#142D3A')
    d.text((25,68),'Light green marks held timber. Dashed red arrows follow the visible jaws and show possible clamping directions.',font=font(20),fill='#425C68')
    for i,e,a,fs in samples:
        f=fs[1]
        box=[(133,162,397,339),(302,208,566,385)][i]
        x=24+i*605
        d.text((x,114),('Left gripper carries the diagonal timber','Right gripper steadies the other timber')[i],font=font(22,True),fill='#142D3A')
        tile=detail_image(i,f,box,582,390,b.COLORS[1])
        im.paste(tile,(x,151))
    im.save(D/'review.jpg',quality=96,subsampling=0)

if __name__=='__main__':
    b.register_fonts()
    data=list(read())
    for _,e,a,fs in data:
        for f in fs:
            meta=next(k for k in e['frames'] if k['role']==f.role)
            with f.photo.open('rb') as h:assert hashlib.file_digest(h,'sha256').hexdigest()==meta['sha256']
    with SOURCE.open('rb') as h:assert hashlib.file_digest(h,'sha256').hexdigest()==data[0][1]['source_sha256']
    c=canvas.Canvas(str(D/'review.pdf'),pagesize=(b.PAGE_W,b.PAGE_H),pageCompression=1)
    c.setTitle('V04 | Held timber and possible clamping directions')
    for i,e,a,fs in data:build(c,i,e,a,fs)
    c.save()
    preview(data)
