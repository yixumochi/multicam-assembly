"""Reproduce the read-only native-frame extraction. Existing source frames are protected."""
import av,json,hashlib,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
targets=[27,30,33,36,39,42,45,48,213,216,219,222];rows=[]
with av.open(str(a.video)) as c:
 for index,f in enumerate(c.decode(video=0)):
  if f.pts is None:continue
  seconds=float(f.pts*f.time_base)
  if targets and seconds>=targets[0]:
   t=targets.pop(0);path=a.out/('video_%03ds.jpg'%t)
   if path.exists():raise FileExistsError(path)
   f.to_image().save(path,quality=97)
   rows.append(dict(frame=index,pts=f.pts,time_base=str(f.time_base),seconds=seconds,file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
  if not targets:break
assert not targets,'Video ended before requested frames'
(a.out/'manifest.json').write_text(json.dumps(rows,indent=2))
(a.out/'video_receipt.json').write_text(json.dumps(dict(path=str(a.video.resolve()),sha256=hashlib.sha256(a.video.read_bytes()).hexdigest()),indent=2))
