from PIL import Image,ImageDraw
from board_paths import V04_VIDEO
import render_boards as b

D=b.WORK/'grip_review'
SOURCE=V04_VIDEO
ROIS={437:((143,170,304,320),(405,208,513,387)),538:((182,184,342,340),(405,208,513,387)),639:((219,214,379,387),(405,208,513,387))}
IDS=('E-656081cd849333','E-df1e5ad54fb77c')
if __name__=='__main__':
    import cv2

    D.mkdir(parents=True, exist_ok=True)
    cap=cv2.VideoCapture(str(SOURCE))
    for n in ROIS:
        cap.set(cv2.CAP_PROP_POS_FRAMES,n)
        ok,arr=cap.read()
        assert ok
        im=Image.fromarray(arr[:,:,::-1])
        for i,roi in enumerate(ROIS[n]):
            sub=im.crop(tuple(k*2 for k in roi))
            sub=sub.resize((sub.width*2,sub.height*2))
            d=ImageDraw.Draw(sub)
            for x in range(((roi[0]+9)//10)*10,roi[2],10):
                p=(x-roi[0])*4
                d.line((p,0,p,6),fill='#F0D180')
                d.text((p,7),str(x),fill='white',stroke_width=1,stroke_fill='black')
            for y in range(((roi[1]+9)//10)*10,roi[3],10):
                p=(y-roi[1])*4
                d.line((0,p,6,p),fill='#F0D180')
                d.text((4,p),str(y),fill='white',stroke_width=1,stroke_fill='black')
            sub.save(D/f'{n}_{i}_detail.jpg',quality=95)
    for i,eid in enumerate(IDS):
        e,a=b.load_case('V04',b.WORK/'annotations/V04.json',eid,False)[0]
        tiles=[]
        for f in b.load_frames(e,a,False):
            mask=Image.open(b.WORK/'pilot'/f'V04_{f.number}_pilot_mask.png') if i==0 else f.mask
            im=Image.open(f.photo).convert('RGB')
            v=Image.composite(Image.new('RGB',im.size,'#35d3aa'),im,mask.point(lambda p:int(p*.67)))
            tiles.append(v.crop((90,0,511,513) if i==0 else (385,0,506,513)))
        out=Image.new('RGB',(sum(v.width for v in tiles),513),'white')
        for j,v in enumerate(tiles):out.paste(v,(j*v.width,0))
        out.save(D/f'candidate{i}.jpg',quality=95)
