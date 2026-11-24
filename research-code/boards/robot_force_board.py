from copy import deepcopy
from dataclasses import dataclass
from math import hypot
from pathlib import Path
import hashlib
from PIL import Image,ImageDraw,ImageFont,ImageChops
from reportlab.pdfgen import canvas
from grip_board import proj,endpoint,DETAIL
from grip_geometry import UPPER,LOWER,REF,TIMBER,approx
from grip_inspect import IDS
from machine_board import tint,crop,overlay_card,HIGHLIGHT
import render_boards as b

D=b.WORK/'robot_force_review'
NAMES=('Left robot and timber gripper','Right robot and timber gripper')
CA,CB,CR='#AF392A','#175C94','#0B6F50'
INK='#142D3A'
MUTED='#4F6570'

def point(z):return (z.real,z.imag)
def cross(a,bv):return (a.conjugate()*bv).imag
def unit(line):
    dz=complex(line[2]-line[0],line[3]-line[1])
    return dz/abs(dz)

@dataclass
class Grip:
    a:complex
    bpos:complex
    ua:complex
    ub:complex
    @property
    def resultant(self):return self.ua+self.ub
    @property
    def application(self):
        # Put the equivalent arrow on AB by matching its moment about A.
        d=self.bpos-self.a
        t=cross(d,self.ub)/cross(d,self.resultant)
        assert 0 <= t <= 1
        p=self.a+t*d
        assert abs(cross(p-self.a,self.resultant)-cross(d,self.ub))<1e-9
        return p

def model(i,n):
    mask=Image.open(b.WORK/'grip_review'/f'wood_{i}_{n}.png')
    la,lb=UPPER[i][n],LOWER[i][n]
    return Grip(complex(*endpoint(mask,la)),complex(*endpoint(mask,lb)),unit(la),unit(lb))
def font(size,bold=False):
    return ImageFont.truetype(b.font_path(bold), size)
def arrow(draw,p,q,color,width,halo=False):
    dp=q-p
    u=dp/abs(dp)
    h=min(4.2*width,.26*abs(dp))
    pts=[point(q-u*h+1j*u*.55*h),point(q),point(q-u*h-1j*u*.55*h)]
    if halo:
        draw.line([point(p),point(q)],fill='white',width=width+3)
        draw.line(pts,fill='white',width=width+3,joint='curve')
    draw.line([point(p),point(q)],fill=color,width=width)
    draw.line(pts,fill=color,width=width,joint='curve')
def tag(draw,xy,label,col,size):
    f=font(size,True)
    x,y=xy
    box=draw.textbbox((x,y),label,font=f,anchor='mm')
    draw.rounded_rectangle((box[0]-4,box[1]-3,box[2]+4,box[3]+3),radius=4,fill=col,outline='white',width=1)
    draw.text((x,y),label,font=f,anchor='mm',fill='white')

def detail_image(f,g,box,size,show_sum):
    w,h=size
    im=Image.open(f.photo).convert('RGB').transform(size,Image.Transform.EXTENT,box,Image.Resampling.BICUBIC)
    draw=ImageDraw.Draw(im)
    def trans(z):return complex(*proj(point(z),box,0,0,w,h))
    # Same scale for the contact vectors and their resultant in this image.
    force_scale=w/(box[2]-box[0])*18
    for loc,u,color,lab in ((g.a,g.ua,CA,'A'),(g.bpos,g.ub,CB,'B'),(g.application,g.resultant,CR,'R')):
        if lab=='R' and not show_sum:continue
        p=trans(loc)
        width=max(3,round(w/140))
        arrow(draw,p,p+u*force_scale,color,width,True)
        rr=max(3,round(width*.9))
        draw.ellipse((p.real-rr,p.imag-rr,p.real+rr,p.imag+rr),fill='white',outline=color,width=2)
        offset=u/abs(u)*(-3.6*width)
        tag(draw,point(p+offset),lab,color,max(12,round(w/29)))
    return im

def construction(g,w,h,cn=False):
    im=Image.new('RGB',(w,h),'#F5F8FA')
    draw=ImageDraw.Draw(im)
    s=min(w*.255,h*.33)
    p=0j;q=s*g.ua;z=q+s*g.ub
    gap=complex(0,round(h*.23))
    pts=(p,q,z,p+gap,z+gap)
    minx,maxx=min(k.real for k in pts),max(k.real for k in pts)
    miny,maxy=min(k.imag for k in pts),max(k.imag for k in pts)
    off=complex(w/2-(minx+maxx)/2,h*.50-(miny+maxy)/2)
    p,q,z=p+off,q+off,z+off
    for a,bb in ((p,p+gap),(z,z+gap)):
        for offy in range(0,int(gap.imag),7):
            vv=a+offy*1j
            draw.line((point(vv),point(a+min(gap.imag,offy+3)*1j)),fill='#93AAB0',width=2)
    weight=max(3,round(w/110))
    arrow(draw,p,q,CA,weight)
    arrow(draw,q,z,CB,weight)
    arrow(draw,p+gap,z+gap,CR,weight)
    fs=font(max(14,round(w/22)),True)
    for loc,caption,color,dy in (((p+q)/2,'FA',CA,-h*.14),((q+z)/2,'FB',CB,-h*.14),((p+z)/2+gap,'R',CR,h*.14)):
        draw.text(point(loc+dy*1j),caption,font=fs,fill=color,anchor='mm')
    return im

def data():
    for i,eid in enumerate(IDS):
        e,ann=b.load_case('V04',b.WORK/'annotations/V04.json',eid,False)[0]
        a=deepcopy(ann)
        a['object']=NAMES[i]
        a['note']=('The suspended carriage, robot wrist and moving gripper are included in the mask.' if i==0 else
                   'The visible right robot and its gripper hold the timber throughout these frames.')
        for meta in e['frames']:
            if meta['role'] not in b.ROLES:continue
            n=meta['frame_zero_based']
            mp=(b.WORK/'machine_review'/f'{n}_mask.png') if i==0 else (D/f'right_{n}.png')
            a['frames'][meta['role']]['mask']=str(mp)
            with (b.EVIDENCE/meta['image']).open('rb') as h:assert hashlib.file_digest(h,'sha256').hexdigest()==meta['sha256']
            assert ImageChops.multiply(Image.open(mp),Image.open(b.WORK/'grip_review'/f'wood_{i}_{n}.png')).getbbox() is None
        frames=b.load_frames(e,a,False)
        yield i,e,a,frames,[model(i,f.number) for f in frames]

def grids(c,i,frames,gs):
    tw=(b.COL_W-20)/3
    th=tw*9/16
    b.txt(c,'Three source frames',b.MARGIN,168,12,bold=True)
    b.txt(c,'Mechanical arm and gripper mask',b.MARGIN,312,12,bold=True)
    b.txt(c,'Two contacts on the held timber',b.RIGHT,168,12,bold=True)
    for j,(f,color,g) in enumerate(zip(frames,b.COLORS,gs)):
        lx=b.MARGIN+j*(tw+10)
        rx=b.RIGHT+j*(tw+10)
        im=Image.open(f.photo).convert('RGB')
        b.picture(c,im,lx,180,tw,th)
        whole=(0,0,*f.size)
        ln=REF[f.number]
        p,q=[proj(uv,whole,lx,180,tw,th) for uv in (ln[:2],ln[2:])]
        b.segment(c,p,q,b.WHITE,2.1);b.segment(c,p,q,b.REF,1)
        b.circle(c,proj(f.traced('point'),whole,lx,180,tw,th),2.6,b.REF,b.WHITE,1)
        roi=HIGHLIGHT[f.number] if i==0 else (228,0,914,385.875)
        b.picture(c,crop(tint(im,f.mask,color),roi),lx,324,tw,th)
        b.picture(c,detail_image(f,g,DETAIL[i][f.number],(640,360),False),rx,180,tw,th)
        for x in (lx,rx):
            b.segment(c,(x,292),(x+14,292),color,2.2)
            b.txt(c,f'{f.role.capitalize()}  {f.time_label}',x+17,296,9.4,bold=True)

def sum_panel(c,i,f,g):
    x=b.RIGHT
    b.txt(c,'Middle frame   ·   Equal-force model at the two contacts',x,322,12,bold=True)
    width=(b.COL_W-10)/2
    h=width*.63
    bx=([(143,170,412,339.47),(312,210,576,376.32)])[i]
    pic=detail_image(f,g,bx,(720,454),True)
    b.picture(c,pic,x,333,width,h)
    b.picture(c,construction(g,720,454),x+width+10,333,width,h)
    b.txt(c,'A and B are contact locations.',x,333+h+14,8.7,b.MUTED)
    b.txt(c,'FA + FB = R, drawn head to tail.',x+width+10,333+h+14,8.7,b.MUTED,True)

def angles_panel(c,i,frames,gs):
    x=b.RIGHT
    b.txt(c,'On-screen angles to the fixed upright edge',x,548,13,bold=True)
    b.rect(c,x,561,b.COL_W,170,fill=b.CARD,radius=5)
    cols=[x+14,x+120,x+217,x+311,x+405]
    for xx,label in zip(cols,['Sample','Timber edge','FA at A','FB at B','R (1:1 model)']):
        b.txt(c,label,xx,582,9.5,bold=True)
    for j,(f,g,col) in enumerate(zip(frames,gs,b.COLORS)):
        n=f.number;y=610+j*40
        res=g.resultant
        values=[approx(k,REF[n]) for k in (TIMBER[i][n],UPPER[i][n],LOWER[i][n],(0,0,res.real,res.imag))]
        b.segment(c,(cols[0],y-3),(cols[0]+10,y-3),col,2)
        b.txt(c,f.time_label,cols[0]+15,y,9.6,bold=True)
        for k,(xx,v) in enumerate(zip(cols[1:],values)):
            color=(b.INK,b.HexColor(CA),b.HexColor(CB),b.HexColor(CR))[k]
            b.txt(c,f'about {v}°',xx,y,10,color,k==3)
        b.segment(c,(x+12,y+12),(x+b.COL_W-12,y+12))
    b.text_block(c,'Model assumes equal projected force magnitudes along the visible jaw directions. R combines these two contacts only.',x,750,b.COL_W,9,2)

def build(c,i,e,a,fs,gs):
    x=b.MARGIN
    b.txt(c,'MULTICAM  /  V04 ROBOT AND GRIP',x,32,11,b.MUTED,True)
    b.aligned(c,'TWO-EVENT REVIEW',b.PAGE_W-x,32,10,b.MUTED,1,True)
    b.txt(c,('04   Left robot carries the diagonal timber','05   Right robot holds the second timber')[i],x,68,25,bold=True)
    b.txt(c,f"{e['label']}   ·   {e['start']:.2f}–{e['end']:.2f} s",x,94,12,b.MUTED)
    b.aligned(c,f"{e['id']}   ·   task29.mp4   ·   25 fps",b.PAGE_W-x,94,10,b.MUTED,1)
    b.segment(c,(x,112),(b.PAGE_W-x,112))
    b.txt(c,'01   Mechanical arm mask and extent',x,140,16,bold=True)
    b.txt(c,'02   Grasp locations, angles and resultant',b.RIGHT,140,16,bold=True)
    b.segment(c,(b.RIGHT-b.GAP/2,128),(b.RIGHT-b.GAP/2,776))
    grids(c,i,fs,gs);overlay_card(c,a,fs,e);sum_panel(c,i,fs[1],gs[1]);angles_panel(c,i,fs,gs)
    b.segment(c,(x,778),(b.PAGE_W-x,778))
    b.txt(c,'Source  task29.mp4, frames 000437 / 000538 / 000639, 960 × 540 px.',x,798,9,b.MUTED)
    b.txt(c,'The brown upright edge is the shared 0° reference. Smaller angles are rounded to 5°. Contact force magnitudes are unmeasured.',x,814,9,b.MUTED)
    b.aligned(c,f'Review {i+1} / 2',b.PAGE_W-x,814,9,b.MUTED,1)
    c.showPage()

def preview(sample):
    i,e,a,fs,gs=sample
    f=fs[1];g=gs[1]
    width=1320
    vis=Image.new('RGB',(width,563),'#F5F8FA')
    draw=ImageDraw.Draw(vis)
    draw.text((24,20),'Left  |  Robot arm and gripper masks',font=font(27,True),fill=INK)
    draw.text((665,20),'Right  |  Contacts A, B and resultant',font=font(27,True),fill=INK)
    raw=Image.open(f.photo).convert('RGB')
    box=(65,0,758,355)
    tile=tint(raw,f.mask,b.COLORS[1]).transform((620,318),Image.Transform.EXTENT,box,Image.Resampling.BICUBIC)
    vis.paste(tile,(24,81))
    box=(166,174,388,332)
    vis.paste(detail_image(f,g,box,(353,251),True),(666,110))
    vis.paste(construction(g,268,235),(1032,121))
    draw.text((25,414),'V04 · Event 04 · Middle frame 000538 · 21.52 s',font=font(18),fill=MUTED)
    draw.text((665,389),'Red and blue show assumed contact forces. Green R is their sum.',font=font(17),fill=MUTED)
    draw.line((24,461,width-24,461),fill='#C7D5D9',width=2)
    draw.text((24,483),'The two image-plane forces are assumed equal and follow the visible jaws toward the timber.',font=font(21),fill=INK)
    r=g.resultant
    degrees_to_edge=approx((0,0,r.real,r.imag),REF[f.number])
    draw.text((24,523),f'The smaller angle between green R and the upright timber reference edge is about {degrees_to_edge}°.',font=font(19),fill=MUTED)
    vis.save(D/'preview.jpg',quality=96,subsampling=0)

if __name__=='__main__':
    b.register_fonts()
    samples=list(data())
    c=canvas.Canvas(str(D/'robot_force.pdf'),pagesize=(b.PAGE_W,b.PAGE_H),pageCompression=1)
    c.setTitle('V04 | Mechanical arm masks and two-contact force resultants')
    for sample in samples:build(c,*sample)
    c.save()
    preview(samples[0])
