import json,sys,hashlib,math
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;O=P/'model_run04'
sys.path.insert(0,str(Path.cwd()/'outputs/dfd_resource_audit_20261001/reader_lib'))
import rhino3dm as rh
v=json.loads((O/'validation.json').read_text());checks=[]
for r in v['files']:
 f=O/r['file'];doc=rh.File3dm.Read(str(f));objs=list(doc.Objects)
 assert all(isinstance(o.Geometry,rh.Brep) and o.Geometry.IsSolid and o.Geometry.IsValid for o in objs)
 assert len(objs)==r['valid_closed_breps'];assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256']
 checks.append(dict(file=r['file'],valid_closed_breps=len(objs),mesh_objects=0,units=str(doc.Settings.ModelUnitSystem),bytes=f.stat().st_size,sha256=r['sha256']))
axes=json.loads((O/'pin_axes.json').read_text());starts=np.array([a['start'] for a in axes]);ends=np.array([a['end'] for a in axes]);radii=np.array([a['radius'] for a in axes])
def distance(p,q,r,s):
 u=q-p;v=s-r;w=p-r;a=u@u;b=u@v;c=v@v;d=u@w;e=v@w;den=a*c-b*b
 ss=np.clip((b*e-c*d)/den,0,1) if den>1e-15 else 0.;tt=(b*ss+e)/c
 if tt<0:tt=0;ss=np.clip(-d/a,0,1)
 elif tt>1:tt=1;ss=np.clip((b-d)/a,0,1)
 return float(np.linalg.norm(w+ss*u-tt*v))
low=np.minimum(starts,ends)-radii[:,None];high=np.maximum(starts,ends)+radii[:,None];collisions=[];candidates=0
for i in range(len(axes)):
 ids=np.where(np.all(low[i]<=high,axis=1)&np.all(low<=high[i],axis=1)&(np.arange(len(axes))>i))[0]
 for j in ids:
  candidates+=1;gap=distance(starts[i],ends[i],starts[j],ends[j])-radii[i]-radii[j]
  if gap<0:collisions.append(dict(pins=[axes[i]['id'],axes[j]['id']],capsule_gap=gap))
result=dict(files=checks,rhino3dm_version=rh.__version__,pin_pin_capsule_candidates=candidates,pin_pin_capsule_overlap_candidates=collisions,pin_pin_status='PASS conservative capsules disjoint' if not collisions else 'requires native solid intersection',graph_component_sizes=v['graph_component_sizes'])
(O/'independent_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
