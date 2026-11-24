"""Discretize recovered curves. Section sizes, segmentation and hole layout are assumptions."""
from pathlib import Path
import json,math
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d
P=Path(__file__).resolve().parent
rows=json.loads((P/'recovered_paths.json').read_text()); full=sorted([r for r in rows if r['full']],key=lambda r:r['order'])
LENGTH=.65;WIDTH=.10;THICK=.024;TRIM=.018;BORE=.006;PIN=.0055
def interp(x,t,v):return np.array([np.interp(x,t,v[:,k]) for k in range(v.shape[1])])
for r in rows:
 r['p']=np.array(r['xyz']);r['p'][:,2]=gaussian_filter1d(r['p'][:,2],.8)
 r['u']=np.maximum.accumulate(np.array(r['u']));r['u']+=np.arange(101)*1e-9
 r['d']=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['p'],axis=0),axis=1))]
 r['total']=r['d'][-1]
def position(r,u):return interp(u,r['u'],r['p'])
def order(r,u):
 if r['full']:return r['order']
 p=position(r,u); ds=sorted((np.linalg.norm((position(f,u)-p)[:2]),f['order'],position(f,u)) for f in full)
 _,i,a=ds[0];_,j,b=ds[1];v=(b-a)[:2];t=np.dot((p-a)[:2],v)/max(np.dot(v,v),1e-12)
 return i+np.clip(t,0,1)*(j-i)
slats=[];byid={}
for r in rows:
 rank=order(r,float(np.mean(r['u'])));r['rank']=rank;phase=(int(rank*2)%3)/3
 # One reusable discretization; boundaries and branch extents remain source-derived.
 cuts=np.r_[0,np.arange((.5+phase)*LENGTH,r['total']-.12,LENGTH),r['total']]
 if len(cuts)>2 and cuts[-1]-cuts[-2]<.18:cuts=np.delete(cuts,-2)
 # Merge boundary stubs that had no feasible paired-dowel connection in the first pass.
 if r['id'] in ['L11','L16','L17'] and len(cuts)>2:cuts=np.delete(cuts,-2)
 if r['id'] in ['L54','L62','L63','L65','L67','L72'] and len(cuts)>2:cuts=np.delete(cuts,1)
 r['pieces']=[]
 vertices=np.array([interp(c,r['d'],r['p']) for c in cuts]);dirs=np.diff(vertices,axis=0);dirs/=np.linalg.norm(dirs,axis=1)[:,None]
 trims=[TRIM]
 for va,vb in zip(dirs[:-1],dirs[1:]):
  theta=np.arccos(np.clip(va@vb,-1,1));trims.append(max(TRIM,np.hypot(WIDTH,THICK)/2*np.tan(theta/2)+.004))
 trims.append(TRIM)
 for k,(lo,hi) in enumerate(zip(cuts[:-1],cuts[1:])):
  a=interp(lo,r['d'],r['p']);b=interp(hi,r['d'],r['p']);v=b-a;length=np.linalg.norm(v);v/=length
  side=np.array([-v[1],v[0],0.]);side/=np.linalg.norm(side)
  radial=np.cross(side,v);radial/=np.linalg.norm(radial)
  a=a+v*trims[k];b=b-v*trims[k+1]
  u0=float(np.interp(lo+trims[k],r['d'],r['u']));u1=float(np.interp(hi-trims[k+1],r['d'],r['u']))
  s=dict(id=r['id']+'_S%02d'%(k+1),path=r['id'],a=a.tolist(),b=b.tolist(),radial=radial.tolist(),width=WIDTH,thickness=THICK,u0=u0,u1=u1,nodes=[])
  r['pieces'].append(s);slats.append(s);byid[s['id']]=s
def piece(r,u):
 for s in r['pieces']:
  if s['u0']+.004<u<s['u1']-.004:return s
def on_slat(s,u):return np.array(s['a'])+(np.array(s['b'])-s['a'])*((u-s['u0'])/(s['u1']-s['u0']))
pair_samples={}
for u in np.linspace(.003,.997,1600):
 active=[]
 for r in rows:
  if r['u'][0]<=u<=r['u'][-1]:
   s=piece(r,u)
   if s:active.append((r['rank'],r,s))
 active.sort(key=lambda x:x[0])
 for (_,a,sa),(_,b,sb) in zip(active[:-1],active[1:]):
  if np.linalg.norm(on_slat(sa,u)-on_slat(sb,u))>.40:continue
  key=(sa['id'],sb['id']);pair_samples.setdefault(key,[]).append(float(u))
nodes=[];axes=[];rejected=[];hole_centers={s['id']:[] for s in slats}
# Conservative stock-box collision screening before any native Boolean work.
centers=[];bases=[];halves=[]
for s in slats:
 a=np.array(s['a']);b=np.array(s['b']);v=(b-a)/np.linalg.norm(b-a);r=np.array(s['radial']);n=np.cross(v,r)
 centers.append((a+b)/2);bases.append(np.array([v,r,n]));halves.append([np.linalg.norm(b-a)/2,WIDTH/2,THICK/2])
centers=np.array(centers);bases=np.array(bases);halves=np.array(halves);indices={s['id']:i for i,s in enumerate(slats)}
accepted_axes=[];axis_low=np.zeros((10000,3));axis_high=np.zeros((10000,3))
def segment_distance(p,q,r,s):
 u=q-p;v=s-r;w=p-r;a=u@u;b=u@v;c=v@v;d=u@w;e=v@w;den=a*c-b*b
 ss=np.clip((b*e-c*d)/den,0,1) if den>1e-15 else 0.;tt=(b*ss+e)/c
 if tt<0:tt=0;ss=np.clip(-d/a,0,1)
 elif tt>1:tt=1;ss=np.clip((b-d)/a,0,1)
 return np.linalg.norm(w+ss*u-tt*v)
def expanded_axis(p,q,ai,bi):
 d=(q-p)/np.linalg.norm(q-p)
 def exitdist(i,p,d):
  local=bases[i]@(p-centers[i]);v=bases[i]@d
  return min(((np.where(v>0,halves[i],-halves[i])-local)/np.where(abs(v)>1e-10,v,1e-10))[abs(v)>1e-10])
 return p-d*(exitdist(ai,p,-d)+PIN*.5),q+d*(exitdist(bi,q,d)+PIN*.5)
def stock_clear(p,q,ai,bi):
 p0,p1=expanded_axis(p,q,ai,bi)
 local=np.einsum('nij,nj->ni',bases,p0-centers);v=np.einsum('nij,j->ni',bases,p1-p0)
 hv=halves+PIN+1e-5;vs=np.where(abs(v)<1e-12,1e-12,v)
 t0=(-hv-local)/vs;t1=(hv-local)/vs
 low=np.maximum(np.minimum(t0,t1).max(1),0);high=np.minimum(np.maximum(t0,t1).min(1),1)
 hits=low<=high;hits[ai]=False;hits[bi]=False
 return not np.any(hits)
def pins_clear(p,q,ai,bi):
 p0,p1=expanded_axis(p,q,ai,bi);n=len(accepted_axes)
 lo=np.minimum(p0,p1)-PIN;hi=np.maximum(p0,p1)+PIN
 candidates=np.where(np.all(axis_low[:n]<=hi,axis=1)&np.all(lo<=axis_high[:n],axis=1))[0]
 return all(segment_distance(p0,p1,*accepted_axes[j])>2*PIN+.0005 for j in candidates)
for (aid,bid),us in sorted(pair_samples.items()):
 a,b=byid[aid],byid[bid];lo,hi=min(us),max(us)
 if np.linalg.norm(on_slat(a,hi)-on_slat(a,lo))<.055 or np.linalg.norm(on_slat(b,hi)-on_slat(b,lo))<.055:
  rejected.append(dict(slats=[aid,bid],reason='insufficient overlap for two separated holes'));continue
 proposals=[]
 for fractions in [[.28,.72],[.15,.6],[.4,.85],[.12,.88],[.2,.5],[.5,.8]]:
  proposals=[]
  for f in fractions:
   u=lo+(hi-lo)*f;p=on_slat(a,u);q=on_slat(b,u)
   if min([np.linalg.norm(p-x) for x in hole_centers[aid]]+[1])<BORE*3.1 or min([np.linalg.norm(q-x) for x in hole_centers[bid]]+[1])<BORE*3.1:break
   if not stock_clear(p,q,indices[aid],indices[bid]):break
   if not pins_clear(p,q,indices[aid],indices[bid]):break
   proposals.append((p,q))
  if len(proposals)==2:break
 if len(proposals)!=2:
  rejected.append(dict(slats=[aid,bid],reason='hole proximity or intervening timber; no forced connection'));continue
 nid='J%04d'%(len(nodes)+1);pins=[]
 for k,(p,q) in enumerate(proposals):
  did=nid+'_D%d'%(k+1);pins.append(did)
  axes.append(dict(id=did,node=nid,slats=[aid,bid],a=p.tolist(),b=q.tolist(),radius=PIN,bore_radius=BORE))
  p0,p1=expanded_axis(p,q,indices[aid],indices[bid]);ii=len(accepted_axes);accepted_axes.append((p0,p1));axis_low[ii]=np.minimum(p0,p1)-PIN;axis_high[ii]=np.maximum(p0,p1)+PIN
  hole_centers[aid].append(p);hole_centers[bid].append(q)
 nodes.append(dict(id=nid,slats=[aid,bid],dowels=pins,status='interpreted adjacency and hole locations, not author joint IDs'))
 a['nodes'].append(nid);b['nodes'].append(nid)
adj={s['id']:set() for s in slats}
for n in nodes:
 a,b=n['slats'];adj[a].add(b);adj[b].add(a)
components=[];remaining=set(adj)
while remaining:
 stack=[next(iter(remaining))];cc=set()
 while stack:
  a=stack.pop()
  if a in cc:continue
  cc.add(a);stack.extend(adj[a]-cc)
 remaining-=cc;components.append(sorted(cc))
data=dict(slats=slats,nodes=nodes,axes=axes,graph_components=components,rejected=rejected,assumptions=dict(target_slat_length=LENGTH,slat_width=WIDTH,slat_thickness=THICK,end_trim=TRIM,bore_radius=BORE,pin_radius=PIN,units='None',segmentation='generated along image-recovered paths; not exact author segmentation',joint_layout='adjacent active paths with two pins; interpreted, not validated source hole positions'))
(P/'solid_input.json').write_text(json.dumps(data,indent=2))
print(dict(slats=len(slats),nodes=len(nodes),dowels=len(axes),graph_component_sizes=sorted(map(len,components),reverse=True),rejected=len(rejected)))
