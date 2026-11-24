"""Source-derived planar paths and regularized height fit. No metric calibration."""
import json, math
from pathlib import Path
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d, distance_transform_edt, map_coordinates
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
P=Path(__file__).resolve().parent
def save(name,x): (P/name).write_text(json.dumps(x,indent=2),encoding='utf-8')
im=cv2.imread(str(P/'source/video_033s.jpg')); g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
mask=((g>85)&(g<200)).astype('uint8')*255
mask[:145]=0;mask[980:]=0;mask[:,:590]=0;mask[:,1410:]=0
mask=cv2.erode(mask,np.ones((3,3),np.uint8))
n,lab,stats,cent=cv2.connectedComponentsWithStats(mask)
short=set([2,4,6,8,11,13,15,17,20,24,27,31,34]+list(range(64,87)))
paths=[]
for j,st in enumerate(stats[1:],1):
 if st[4]<90 or max(st[2:4])<40: continue
 yy,xx=np.where(lab==j); pts=np.c_[xx,yy].astype(float); mean=pts.mean(0)
 _,_,v=np.linalg.svd(pts-mean,full_matrices=False); t=(pts-mean)@v[0]; ids=np.floor(t/2).astype(int)
 a=np.array([pts[ids==k].mean(0) for k in sorted(set(ids))]);a=gaussian_filter1d(a,.7,axis=0)
 if a[0,1]<a[-1,1]:a=a[::-1]
 d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(a,axis=0),axis=1))]; u=np.linspace(0,1,101)
 xy=np.c_[np.interp(u*d[-1],d,a[:,0]),np.interp(u*d[-1],d,a[:,1])]
 paths.append(dict(id=j,full=j not in short,xy=xy))
full=[r for r in paths if r['full']]
# Order by position along the observed outer footprint: left leg, rounded corner, right leg.
full.sort(key=lambda r: math.atan2(r['xy'][0,1]-400,r['xy'][0,0]-1000),reverse=True)
for i,r in enumerate(full): r['order']=i;r['u']=np.linspace(0,1,101)
M=np.linalg.solve(np.array([[608,450,1],[925,957,1],[1385,663,1.]]),np.array([[468,550],[921,961],[1402,642.]]))
# Camera is treated as an orthographic approximation; scale inferred from ground affine axes.
zscale=float(np.sqrt(np.linalg.norm(M[:2,0])**2-np.linalg.norm(M[:2,1])**2))*100
tree=cKDTree(np.concatenate([r['xy'] for r in full])); lookup=[(i,k/100) for i in range(len(full)) for k in range(101)]
for r in paths:
 if not r['full']:
  _,ind=tree.query(r['xy']);r['near']=np.array([lookup[k][0] for k in ind]);r['u']=np.array([lookup[k][1] for k in ind])
 else:r['near']=np.full(101,r['order'])
 r['ground']=np.c_[r['xy'],np.ones(101)]@M
blue=cv2.imread(str(P/'source/video_036s.jpg'))
b,gg,rr=cv2.split(blue);bm=(b.astype(float)>rr+45.)&(b.astype(float)>gg+30.)&(rr<150)
dist=distance_transform_edt(~bm)
sy,sx=np.where(bm); blue_samples=np.c_[sx,sy][::25]
end_traces={1:np.array([[468,550],[483,503],[501,455],[526,401],[556,345],[588,293],[620,258],[647,239],[672,235],[698,238],[728,246],[760,255]]),16:np.array([[1402,641],[1397,556],[1379,487],[1356,450],[1340,411],[1313,369],[1297,362],[1269,375],[1232,404]])}
valley=np.array([[809,501],[824,519],[851,529],[880,534],[910,539],[935,536],[960,524],[987,520],[1010,523],[1045,521],[1073,514],[1103,497]])
save('manual_axon_constraints.json',{'source':'source/video_036s.jpg','end_profiles':{str(k):v.tolist() for k,v in end_traces.items()},'inner_visible_outline':valley.tolist(),'method':'manual pixel tracing, approximate 3-6 px uncertainty; fitting evidence not independent ground truth'})
def project(r,h,exponent):
 z=h[r['near']]*np.sin(np.pi*r['u'])**exponent
 return r['ground']-np.c_[np.zeros(101),z*zscale],z
def loss(x):
 h=x[:-1];e=x[-1];out=[];projected=[]
 for r in paths:
  q,z=project(r,h,e); projected.append(q);out.extend(map_coordinates(dist,[q[:,1],q[:,0]],order=1,mode='nearest')[3:-3:2])
  if r['id'] in end_traces:
   out.extend(cKDTree(q).query(end_traces[r['id']])[0]*3)
 qt=cKDTree(np.concatenate(projected));out.extend(qt.query(blue_samples)[0]*.6);out.extend(qt.query(valley)[0]*4)
 # Smooth height variation, not an author equation. Endpoint height prior from clear end profiles.
 out.extend(np.diff(h,2)*60)
 return np.array(out)
best=None
for hh in [2.,2.6]:
 x=np.r_[np.full(len(full),hh),.65]
 fit=least_squares(loss,x,bounds=(np.r_[np.full(len(full),.7),.35],np.r_[np.full(len(full),4.),1.5]),max_nfev=90,diff_step=.003)
 if best is None or np.mean(fit.fun**2)<best[0]:best=(np.mean(fit.fun**2),fit.x)
h=best[1][:-1];e=best[1][-1]
out=[];allerr=[]
for r in paths:
 q,z=project(r,h,e);err=map_coordinates(dist,[q[:,1],q[:,0]],order=1,mode='nearest');allerr.extend(err)
 xyz=np.c_[(r['xy'][:,0]-1000)/100,(600-r['xy'][:,1])/100,z]
 out.append(dict(id='L%02d'%r['id'],component=r['id'],full=r['full'],order=r.get('order'),xy=r['xy'].tolist(),u=r['u'].tolist(),xyz=xyz.tolist(),projected=q.tolist(),fit_error_median_px=float(np.median(err))))
save('recovered_paths.json',out)
save('form_fit.json',dict(status='SOURCE_IMAGE_CONSTRAINED_INTERPRETATION',source_plan='source/video_033s.jpg',source_elevation='source/video_036s.jpg',paths=len(paths),full_paths=len(full),partial_paths=len(paths)-len(full),ground_affine=M.tolist(),vertical_pixels_per_unit=zscale,height_model='h(path) * sin(pi*u)**exponent; smoothness regularized, NOT author algorithm',height_values=h.tolist(),exponent=float(e),median_oneway_blue_distance_px=float(np.median(allerr)),p90_oneway_blue_distance_px=float(np.percentile(allerr,90)),metric_scale=None,not_independent_validation=True,assumptions=['orthographic camera with vertical projected Z','arbitrary model unit equals 100 plan-image pixels','partial path height interpolated from nearest full paths','remaining blue-distance ambiguity; no exact author 3D vertices'],classification='50 full + 36 partial traces; source linework, not 86 prefab modules'))
for name,source,field in [('plan_overlay','video_033s.jpg','xy'),('axon_overlay','video_036s.jpg','projected')]:
 bg=cv2.imread(str(P/'source'/source));overlay=bg.copy()
 for r in out:cv2.polylines(overlay,[np.rint(r[field]).astype('int32')],False,(0,140,255),2)
 cv2.imwrite(str(P/(name+'.jpg')),cv2.addWeighted(bg,.35,overlay,.65,0))
print(json.dumps(json.loads((P/'form_fit.json').read_text()),indent=2))
