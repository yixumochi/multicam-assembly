from copy import deepcopy
import hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageChops,ImageFilter
from reportlab.pdfgen import canvas
import render_boards as b
from machine_refine import D,boxes

EVENTS=('E-656081cd849333','E-4d4ad4d1c2f948')
SUBJECT=('Left overhead robot and timber gripper','Handheld power driver')
NOTES=('The left gripper carries the diagonal timber. Its far jaw is hidden. The insertion direction at the upper joint cannot be resolved.',
       'The exposed driver is visible between the hands. The supporting palm is traced separately at the chuck. The feed follows the working axis.')
EDGES=('Long steel guide on the gripper carriage','Working axis from chuck to timber')
DETAILS={
 437:(115,153,415,321.75),538:(163,180,443,337.5),639:(202,232,462,378.25),
 640:(332,288,549,410.0625),667:(332,288,549,410.0625),694:(332,288,549,410.0625)}
HIGHLIGHT={
 437:(78,0,698,348.75),538:(95,0,715,348.75),639:(126,0,806,382.5),
 640:(268,246,600,432.75),667:(268,246,600,432.75),694:(268,246,600,432.75)}
def pages():
    for idx,eid in enumerate(EVENTS):
        e,ann=b.load_case('V04',b.WORK/'annotations/V04.json',eid,False)[0]
        a=deepcopy(ann)
        a['object']=SUBJECT[idx]
        a['note']=NOTES[idx]
        for fmeta in e['frames']:
            role=fmeta['role']
            if role not in b.ROLES: continue
            n=fmeta['frame_zero_based']
            f=a['frames'][role]
            f['mask']=str(D/f'{n}_mask.png')
            path=b.EVIDENCE/fmeta['image']
            with open(path,'rb') as handle:
                assert hashlib.file_digest(handle,'sha256').hexdigest()==fmeta['sha256']
            f['tool_edge']=EDGES[idx]
            if idx==0:
                f['member']={437:[333,492,400,111],538:[336,489,404,105],639:[337,489,405,105]}[n]
                f['member_edge']='Left edge of the receiving upright'
                endpoints={437:(128,526,215,405),538:(162,594,237,439),639:(181,673,257,523)}[n]
                bx,by=boxes[n][:2]
                f['tool']=[round(bx+endpoints[0]/2,1),round(by+endpoints[1]/2,1),round(bx+endpoints[2]/2,1),round(by+endpoints[3]/2,1)]
                f['note']={'start':'The timber is still clear of the upper joint.','middle':'The robot is approaching.','end':'The joining ends overlap in projection.'}[role]
            else:
                f['tool']={640:[481,355,504,359],667:[481,354,506,357.5],694:[481,356,505.5,359]}[n]
                f['force']=f['tool'].copy()
                f['force_along_tool']=True
                f['member_edge']='Left edge of the receiving timber'
                f['note']=None
        yield idx,e,a,b.load_frames(e,a,False)

def crop(im,box):
    return im.transform((800,450),Image.Transform.EXTENT,box,Image.Resampling.BICUBIC)
def tint(im,mask,color):
    rgb=tuple(round(getattr(color,key)*255) for key in ('red','green','blue'))
    inside=Image.composite(Image.new('RGB',im.size,rgb),im,mask.point(lambda z:round(z*.59)))
    edge=ImageChops.subtract(mask,mask.filter(ImageFilter.MinFilter(3)))
    return Image.composite(Image.new('RGB',im.size,rgb),inside,edge.point(lambda v:round(v*.73)))
def mapped(ln,box,x,y,w,h):
    l,t,r,bot=box
    return [(x+(px-l)*w/(r-l),y+(py-t)*h/(bot-t)) for px,py in (ln[:2],ln[2:])]
def draw_traces(c,f,box,x,y,w,h,color):
    c.saveState()
    clip=c.beginPath()
    clip.rect(x,b.PAGE_H-y-h,w,h)
    c.clipPath(clip,stroke=0)
    for key in ('member','tool','force','grip'):
        if f.traced(key):
            pts=mapped(f.traced(key),box,x,y,w,h)
            b.trace(c,*pts,key,b.REF if key=='member' else color,b.WHITE if key=='member' else b.INK)
    c.restoreState()

def image_grid(c,frames,idx):
    tw=(b.COL_W-20)/3
    th=tw*9/16
    for x,title,sub in ((b.MARGIN,'Three source frames','Machine highlighted in each frame'),
                        (b.RIGHT,'Working end and receiving edge','Machine masks')) :
        b.txt(c,title,x,168,12,bold=True)
        b.txt(c,sub,x,312,12,bold=True)
    for i,(f,col) in enumerate(zip(frames,b.COLORS)):
        x=b.MARGIN+i*(tw+10)
        rx=b.RIGHT+i*(tw+10)
        im=Image.open(f.photo).convert('RGB')
        b.picture(c,im,x,180,tw,th)
        tw2=HIGHLIGHT[f.number]
        b.picture(c,crop(tint(im,f.mask,col),tw2),x,324,tw,th)
        point=f.traced('point')
        if point:
            xy,_=mapped([*point,*point],(0,0,*im.size),x,180,tw,th)
            b.circle(c,xy,2.6,b.REF,b.WHITE,1)
        detail=DETAILS[f.number]
        b.picture(c,crop(im,detail),rx,180,tw,th)
        draw_traces(c,f,detail,rx,180,tw,th,col)
        b.rect(c,rx,324,tw,th,fill=b.CARD)
        b.picture(c,crop(b.colored_mask(f.mask,col,.79),tw2),rx,324,tw,th)
        for tx in (x,rx):
            b.segment(c,(tx,292),(tx+14,292),col,2.2)
            b.txt(c,f'{f.role.capitalize()}  {f.time_label}',tx+18,296,9.5,bold=True)
        b.text_block(c,'Member  '+f.traced('member_edge'),rx,438,tw,8.3,2)
        b.text_block(c,'Tool  '+f.traced('tool_edge'),rx,459,tw,8.3,2)
        if idx==1:
            b.txt(c,'Force follows driver axis',rx,480,8.4,b.MUTED)

def overlay_card(c,a,frames,e):
    x=b.MARGIN
    b.txt(c,'Common point',x,456,11,b.REF,True)
    px,py=frames[1].traced('point')
    b.text_block(c,f"{a['point_label']}, middle frame ({px:g}, {py:g})",x+92,456,b.COL_W-92,9,1)
    b.txt(c,'Highlighted machine   '+a['object'],x,477,11,b.INK,True)
    b.text_block(c,e['description'],x,492,b.COL_W,8.7,2)
    b.txt(c,'Machine masks aligned to the receiving member',x,520,13,bold=True)
    b.rect(c,x,533,b.COL_W,203,fill=b.CARD,radius=5)
    overlay,ref,bounds=b.registered_overlay(frames)
    l,t,r,bot=bounds
    box=(int(min(l,ref[0])-7),int(min(t,ref[1])-7),int(max(r,ref[0])+8),int(max(bot,ref[1])+8))
    img=overlay.crop(box)
    scale=min((b.COL_W-126)/img.width,150/img.height)
    dw,dh=img.width*scale,img.height*scale
    xx,yy=x+(b.COL_W-dw)/2,541+(150-dh)/2
    b.picture(c,img,xx,yy,dw,dh)
    p,q=mapped(bounds,box,xx,yy,dw,dh)
    for u,v in ((p,(q[0],p[1])),((q[0],p[1]),q),(q,(p[0],q[1])),((p[0],q[1]),p)):
        b.segment(c,u,v,b.MUTED,.75,(3,2))
    loc,_=mapped([*ref,*ref],box,xx,yy,dw,dh)
    b.circle(c,loc,2.8,b.REF)
    b.aligned(c,f'W {r-l} px',(p[0]+q[0])/2,q[1]+13,9,b.MUTED,.5,True)
    b.txt(c,f'H {bot-t} px',q[0]+9,(q[1]+p[1])/2,9,b.MUTED,True)
    b.txt(c,'Three translated machine masks. Extent in source-frame pixels.',x+12,724,8.7,b.MUTED)
    b.text_block(c,a['note'],x,752,b.COL_W,9,2)

def board(c,idx,e,a,frames):
    x=b.MARGIN
    n=(4,6)[idx]
    b.txt(c,'MULTICAM  /  V04 MACHINE OBSERVATION',x,32,11,b.MUTED,True)
    b.aligned(c,'TWO-EVENT REVIEW',b.PAGE_W-x,32,10,b.MUTED,1,True)
    b.txt(c,f'{n:02d}   '+SUBJECT[idx],x,68,25,bold=True)
    b.txt(c,f"{e['label']}   ·   {e['start']:.2f}–{e['end']:.2f} s",x,94,12,b.MUTED)
    b.aligned(c,f"{e['id']}   ·   task29.mp4   ·   25 fps",b.PAGE_W-x,94,10,b.MUTED,1)
    b.segment(c,(x,112),(b.PAGE_W-x,112))
    b.txt(c,'01   Relative position and extent',x,140,16,bold=True)
    b.txt(c,'02   Change in angle',b.RIGHT,140,16,bold=True)
    b.segment(c,(b.RIGHT-b.GAP/2,128),(b.RIGHT-b.GAP/2,776))
    image_grid(c,frames,idx)
    overlay_card(c,a,frames,e)
    b.angle_diagram(c,frames)
    if idx:
        b.text_block(c,'The dotted grip line follows the supporting palm below the chuck.',b.RIGHT,751,b.COL_W,9,1)
    b.segment(c,(x,778),(b.PAGE_W-x,778))
    nums=' / '.join(f'{f.number:06}' for f in frames)
    b.txt(c,f'Source  task29.mp4, frames {nums}, 960 × 540 px.',x,798,9,b.MUTED)
    b.txt(c,'Angles are the smaller on-screen angles to the same timber edge, rounded to 5°. Force magnitude is unmeasured.',x,814,9,b.MUTED)
    b.aligned(c,f'Review {idx+1} / 2',b.PAGE_W-x,814,9,b.MUTED,1)
    c.showPage()

def preview(samples):
    canvasw=1340
    image=Image.new('RGB',(canvasw,468),'#F5F8FA')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(b.font_path(True), 25)
    small=ImageFont.truetype(b.font_path(), 18)
    labels=(('Left robot and gripper','V04 · Event 04 · 17.48 s'),('Handheld power driver','V04 · Event 06 · 25.60 s'))
    crops=((75,0,737,372.375),(274,246,549,400.6875))
    for (idx,_,_,frames),title,bb in zip(samples,labels,crops):
        x=22+660*idx
        f=frames[0]
        draw.text((x,15),title[0],font=font,fill='#142D3A')
        im=Image.open(f.photo).convert('RGB')
        highlighted=tint(im,f.mask,b.COLORS[0])
        tile=crop(highlighted,bb).resize((636,358),Image.Resampling.LANCZOS)
        image.paste(tile,(x,65))
        draw.text((x,432),title[1],font=small,fill='#4F6570')
    image.save(D/'preview.jpg',quality=94,subsampling=0)

if __name__=='__main__':
    b.register_fonts()
    samples=list(pages())
    pdf=canvas.Canvas(str(D/'machine.pdf'),pagesize=(b.PAGE_W,b.PAGE_H),pageCompression=1)
    pdf.setTitle('V04 | Machine highlights and working angles')
    for idx,e,a,frames in samples:
        board(pdf,idx,e,a,frames)
        print(e['id'],[(f.number,f.angle_label('tool'),f.angle_label('force')) for f in frames])
    pdf.save()
    preview(samples)
