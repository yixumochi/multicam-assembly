from PIL import Image,ImageChops,ImageDraw
from grip_inspect import D,IDS
import render_boards as b
from math import atan2,degrees

UPPER=(
 {437:(238.5,190,261,204.8),538:(277,209,301,220.4),639:(313,245.5,338,257.5)},
 {437:(466.5,244,434.6,251.2),538:(466.7,244,434.8,251.1),639:(467.2,243.5,435.2,250.8)})
LOWER=(
 {437:(184.5,269,207.9,284.6),538:(235.5,305,257.5,315.4),639:(266,342,293.9,353)},
 {437:(482.5,353.6,455.1,357.4),538:(482.6,353.5,455.2,357.5),639:(483.1,353,455.4,357.2)})
REF={437:(333,492,400,111),538:(336,489,404,105),639:(337,489,405,105)}
TIMBER=(
 {437:(149,364,318,131),538:(211,419,344,153),639:(248,456,363,203)},
 {437:(414,223,451,418),538:(414.1,222.5,451.2,417.7),639:(414.8,222.7,452.0,417.6)})

def getmask(i,f):
    if i==0:
        return Image.open(b.WORK/'pilot'/f'V04_{f.number}_pilot_mask.png').convert('L')
    shape=[(104,120),(112,161),(170,472),(232,797),(292,1168),(285,1176),
           (251,1176),(211,982),(131,554),(82,280),(90,222),(98,161)]
    dx={437:0,538:.1,639:.65}[f.number]
    fence=Image.new('L',f.size)
    native=[(round(378+u/3+dx),round(82+v/3)) for u,v in shape]
    ImageDraw.Draw(fence).polygon(native,fill=255)
    return ImageChops.multiply(f.mask,fence)
def angle(line,ref):
    def slope(s):return degrees(atan2(s[3]-s[1],s[2]-s[0]))
    return abs((slope(line)-slope(ref)+90)%180-90)
def approx(line,ref):
    return int(angle(line,ref)/5+.5)*5
def read():
    D.mkdir(parents=True, exist_ok=True)
    for i,eid in enumerate(IDS):
        e,a=b.load_case('V04',b.WORK/'annotations/V04.json',eid,False)[0]
        fs=b.load_frames(e,a,False)
        for f in fs:
            ma=getmask(i,f)
            ma.save(D/f'wood_{i}_{f.number}.png')
            a['frames'][f.role]['mask']=str(D/f'wood_{i}_{f.number}.png')
        yield i,e,a,b.load_frames(e,a,False)
