import json,math,html,sys,re,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parent;run=sys.argv[1] if len(sys.argv)>1 else 'model_run04';O=P/run
D=P if run=='model_run04' else P/'draft_preview';D.mkdir(exist_ok=True)
V=json.loads((O/'validation.json').read_text());F=json.loads((O/'native_brep_faces.json').read_text());A=json.loads((O/'pin_axes.json').read_text());fit=json.loads((P/'form_fit.json').read_text());inp=json.loads((P/'solid_input.json').read_text())
M=np.array(fit['ground_affine']);zscale=fit['vertical_pixels_per_unit'];sx=np.array([M[0,0]*100,-M[1,0]*100,0]);sy=np.array([M[0,1]*100,-M[1,1]*100,-zscale]);camera=np.cross(sx,-sy);camera/=np.linalg.norm(camera)
def project(points):
 p=np.array(points);ground=np.c_[p[:,0]*100+1000,600-p[:,1]*100,np.ones(len(p))]@M;ground[:,1]-=zscale*p[:,2];return ground
def render(name,faces,axes,node=False):
 allpts=np.concatenate([np.array(f['loops'][0]) for f in faces]);center=allpts.mean(0)
 if node:
  X=np.array([.8,-.6,0]);Y=np.array([-.3,-.4,-.866]);cam=np.cross(X,-Y)
  raw=np.c_[(allpts-center)@X,(allpts-center)@Y];lo=raw.min(0);hi=raw.max(0);sc=min(1200/(hi[0]-lo[0]),800/(hi[1]-lo[1]))
  def pr(p):
   pts=np.array(p)-center;return (np.c_[pts@X,pts@Y]-(lo+hi)/2)*sc+np.array([750,500])
  W,H=1500,1000;lw=sc*axes[0]['radius']*2 if axes else 2
 else:pr=project;cam=camera;W,H=1920,1080;lw=1.25
 layers=[]
 for f in faces:
  points=np.concatenate(f['loops']);depth=float(points.mean(0)@cam);norm=np.array(f['normal']);light=.62+.38*abs(norm@np.array([.2,-.35,.915]));color=tuple(int(x*light) for x in [207,165,108]);loops=[pr(lp) for lp in f['loops']];layers.append((depth,'face',loops,color))
 for a in axes:
  p=np.array([a['start'],a['end']]);layers.append((float(p.mean(0)@cam),'pin',[pr(p)],(35,119,126)))
 layers.sort(key=lambda x:x[0]);img=Image.new('RGB',(W,H),'#f8f5ed');draw=ImageDraw.Draw(img);svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#f8f5ed"/>']
 for _,kind,loops,col in layers:
  if kind=='pin':
   a,b=loops[0];draw.line([tuple(a),tuple(b)],fill=col,width=max(1,round(lw)));svg.append(f'<path d="M{a[0]:.2f},{a[1]:.2f} L{b[0]:.2f},{b[1]:.2f}" fill="none" stroke="rgb{col}" stroke-width="{lw:.2f}"/>');continue
  # Native planar Brep loops; hole masks retain openings without a triangulated mesh.
  pts=np.concatenate(loops);lo=np.floor(pts.min(0)-1).astype(int);hi=np.ceil(pts.max(0)+1).astype(int);size=np.maximum(hi-lo+1,1)
  mask=Image.new('L',tuple(size),0);md=ImageDraw.Draw(mask)
  for j,lp in enumerate(loops):md.polygon([tuple(x-lo) for x in lp],fill=255 if j==0 else 0)
  img.paste(col,tuple(lo),mask)
  path=' '.join('M'+' L'.join('%.2f,%.2f'%tuple(pt) for pt in lp)+' Z' for lp in loops)
  svg.append(f'<path d="{path}" fill="rgb{col}" fill-rule="evenodd" stroke="#725b3e" stroke-width=".22"/>')
 svg.append('</svg>');(D/(name+'.svg')).write_text(''.join(svg));img.save(D/(name+'.png'))
render('full_model',F,A)
focus=V['focus_node'];render('node_detail',[f for f in F if f['id'] in focus['slats']],[a for a in A if a['id'] in focus['dowels']],True)
if run!='model_run04':print(D);sys.exit()
ind=json.loads((O/'independent_validation.json').read_text())
assert not ind['pin_pin_capsule_overlap_candidates'];assert V['graph_component_sizes']==[V['slats']]
V['pin_pin_collision']='PASS conservative capsule screen; see independent_validation.json'
V['independent_validation']='independent_validation.json'
(O/'validation.json').write_text(json.dumps(V,indent=2))
total=V['slats']+V['dowels'];samples=json.loads((P/'source/manifest.json').read_text())
out={
 'case':'V21 / Gradual Assemblies','status':'SOURCE_CONSTRAINED_FULL_FORM_INTERPRETATION',
 'scope':'Entire visible plan-line extent plus source-supported two-dowel joint type. Not exact as-built reconstruction.',
 'source_derived':['86 visible plan paths (50 full + 36 partial) extracted from native frame 1651 at 33s','L/corner footprint and concave inner boundary retained','height fit uses frame 1801 at 36s plus manually traced end profiles and visible inner outline'],
 'assumptions':inp['assumptions'],'author_dimensions':None,'author_model_available':False,
 'source_counts':{'slats':700,'dowels':2700,'prefab_modules':22,'url':'https://gramaziokohler.arch.ethz.ch/web/e/lehre/353.html'},
 'generated_counts':{'slats':V['slats'],'dowels':V['dowels'],'paired_dowel_nodes':V['joints'],'closed_breps':total,'holes':V['holes']},
 'unresolved':['absolute metric scale','unique 3D geometry and exact camera calibration','exact design-diagram versus as-built version correspondence','author member segmentation and per-hole coordinates','22-module seams and anchoring details','structural stability and assembly feasibility'],
 'not_for':['fabrication','source-instance geometry ground truth','metric robot clearance / workspace claims'],
 'validation':ind,'source_samples':samples,'rejected_candidate_connections':len(inp['rejected']),
 'source_fit_is_not_accuracy_test':True,'old_models_preserved':True}
(P/'DELIVERY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(P/'README.txt').write_text('V21 SOURCE-FORM REBUILD\nOpen index.html for evidence and comparisons.\nOpen model_run04/V21_SOURCE_FORM_FULL_CLOSED_BREP.3dm in Rhino.\nUnits: None. Do not interpret dimensions as mm or metres.\nThis is an image-constrained interpretation, not author CAD or fabrication data.\nReproduction: recover_form.py -> prepare_solids.py -> build_source_rhino.py (native Rhino 8) -> independent_check.py -> verify_and_faces_rhino.py (Rhino) -> make_delivery.py.\nNative builder refuses to overwrite existing 3dm files; change output version for a new run.\nEarlier model_run01/02/03 are diagnostic iterations, not final delivery.\n',encoding='utf-8')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V21 · Source-form reconstruction</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f2e9;color:#243632;font:17px/1.75 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1370px;margin:auto;padding:44px 32px}h1{font-size:42px;line-height:1.3}h2{font-size:26px;margin-top:44px}p{max-width:1050px}a{color:#086f76}figure{margin:0;background:#fff;padding:12px;border:1px solid #ddd8cb;border-radius:10px}img{width:100%;display:block}figcaption{font-size:14px;padding:10px} .grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.notice{padding:18px 24px;background:#fff0d0;border-left:5px solid #a76b1f}.good{padding:20px;background:#e3ede7}.btn{display:inline-block;background:#146c70;color:white;padding:11px 20px;border-radius:7px;margin:8px 12px 8px 0;text-decoration:none}.stats{display:flex;gap:14px;flex-wrap:wrap}.stats div{background:white;padding:14px 23px;flex:1}.stats strong{display:block;font-size:30px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}code{font-size:14px}details{background:white;padding:16px;margin:12px 0} .compare{position:relative}.compare img:last-child{position:absolute;top:0;left:0;opacity:.55}input{width:100%}small{color:#52645d}@media(max-width:800px){.grid{grid-template-columns:1fr}main{padding:22px}h1{font-size:30px}}</style><main>
<small>V21 / GRADUAL ASSEMBLIES · SOURCE FORM REBUILD · 2026-10-18</small><h1>Rebuilding from the source drawings in the video</h1>
<p>This reconstruction supersedes the earlier straight-barrel model. It extracts member lines from the plan at 33 seconds, uses the 3D network at 36 seconds to constrain height, and builds straight timber slats with through-holes and double dowels. It covers the legible member lines in the source drawings.</p>
<div class="notice"><b>Model scope: an image-constrained interpretation of the form and its joints.</b> Absolute scale, section sizes, segment boundaries and hole locations are assumptions. The Rhino file uses unitless geometry. Use the model for visual interpretation and topology review.</div>
<p><a class="btn" href="model_run04/V21_SOURCE_FORM_FULL_CLOSED_BREP.3dm">Download the full Rhino model · about 45 MB</a><a class="btn" href="model_run04/V21_SOURCE_FORM_NODE_CLOSED_BREP.3dm">Open the joint extracted from the same model</a><a href="DELIVERY.json">Delivery and source record</a></p>
<div class="stats"><div><strong>__SLATS__</strong>Timber slats</div><div><strong>__PINS__</strong>Timber dowels</div><div><strong>__NODES__</strong>Paired-dowel nodes</div><div><strong>0</strong>Mesh objects</div></div>
<h2>Full reconstructed form</h2><figure><a href="full_model.svg"><img src="full_model.png" alt="Source-constrained full model"></a><figcaption>Projection from loops on the native BRep faces in the final 3DM. Dowel axes and diameters are drawn schematically. The 3DM contains the full solid geometry.</figcaption></figure>
<h2>Source drawing comparison</h2><div class="grid"><figure><img src="source/video_042s.jpg"><figcaption>Source drawing from the video at 42.000 s, used for a visual check.</figcaption></figure><figure><img src="full_model.png"><figcaption>Reconstruction using the same ground-affine projection and an approximate orthographic camera. Sections, segments and holes remain interpretive parameters.</figcaption></figure></div>
<p>The reconstruction retains the curved plan, concave inner boundary, openings at both ends, fan-shaped member directions and local changes in the source drawing.</p>
<div class="grid"><figure><div class="compare"><img src="source/video_036s.jpg"><img id="overlay" src="full_model.png"></div><input type="range" min="0" max="100" value="55" oninput="document.getElementById('overlay').style.opacity=this.value/100"><figcaption>Adjust overlay opacity to compare the overall form.</figcaption></figure><figure><img src="axon_overlay.jpg"><figcaption>Height fit. Orange indicates recovered paths. Blue indicates the source network. Heights remain ambiguous in some overlapping and occluded regions.</figcaption></figure></div>
<h2>Recovering the plan branches</h2><div class="grid"><figure><img src="source/video_033s.jpg"><figcaption>Author plan · source frame 1651 at 33.000 s.</figcaption></figure><figure><img src="plan_overlay.jpg"><figcaption>Extracted paths · 50 full paths and 36 partial paths. These are traced lines.</figcaption></figure></div>
<p>Pixel segmentation, connected components and centerline recovery extract the grey member lines. Full and partial path classifications are in the JSON records. Smooth constraints fit the heights.</p>
<h2>Joint extracted from the full model</h2><div class="grid"><figure><a href="node_detail.svg"><img src="node_detail.png"></a><figcaption>Two slats and two dowels from the rebuilt model. Holes connecting these slats to adjacent members are also visible.</figcaption></figure><div><p>Page 7 of the source PDF, printed page 655, describes two oriented dowels between adjacent slats. The rebuild uses that topology.</p><p>Native Rhino Boolean difference creates the holes. The exported joint preserves the full model's coordinates and object IDs.</p><p><a href="../construction_review01/page_07.png">Source paper page</a> · <a href="model_run04/hole_validation.json">Hole checks by slat</a></p></div></div>
<h2>Verification and evidence limits</h2><table><tr><th>Item</th><th>Result</th></tr><tr><td>Solids</td><td>__TOTAL__ valid closed BReps and zero meshes. Native headless Rhino and rhino3dm both read the model successfully.</td></tr><tr><td>Connection and collision checks</td><td>The graph of __SLATS__ slats is connected. Native solid checks passed for slat-to-slat and dowel-to-slat intersections, as did conservative envelope checks between dowels. Topology and empty-center checks passed for __HOLES__ through-holes.</td></tr><tr><td>Source counts</td><td>The author lists 700 slats, 2700 dowels and 22 modules. This reconstruction contains __SLATS__ slats and __PINS__ dowels. Exact segmentation, seams and individual fasteners still require source data.</td></tr><tr><td>Geometric comparison</td><td>Plan paths come from the source drawing, with height constrained by the 3D drawing. Footage at 213, 216, 219 and 222 seconds supports visual review. Calibrated multi-view validation remains open.</td></tr><tr><td>Missing evidence</td><td>Absolute scale, source coordinates, sections, hole locations, module seams and base details require further evidence.</td></tr><tr><td>Engineering validation</td><td>Fabrication tolerances, structural load, deformation, assembly order and robot reachability require separate checks.</td></tr></table>
<p><a href="https://gramaziokohler.arch.ethz.ch/web/e/lehre/353.html">Author project and reported counts</a> · <a href="model_run04/validation.json">Native checks</a> · <a href="model_run04/independent_validation.json">Independent check and SHA-256</a> · <a href="source/manifest.json">Source frames and hashes</a></p>
<h2>Built form in the video</h2><div class="grid"><figure><img src="source/video_213s.jpg"><figcaption>Built source · 213 s</figcaption></figure><figure><img src="source/video_222s.jpg"><figcaption>Built source · 222 s</figcaption></figure></div>
<details><summary>Reproduction steps and assumptions</summary><p><a href="recover_form.py">recover_form.py</a> · <a href="prepare_solids.py">prepare_solids.py</a> · <a href="build_source_rhino.py">build_source_rhino.py</a> · <a href="independent_check.py">independent_check.py</a> · <a href="verify_and_faces_rhino.py">verify_and_faces_rhino.py</a> · <a href="make_delivery.py">make_delivery.py</a></p><p>Target lengths, sections, gaps, bore and dowel radii, and hole selection are interpretive parameters. Short branch ends that cannot form a double-dowel connection merge into the adjoining segment. See <a href="solid_input.json">solid_input.json</a> for rejected candidates. The native script protects existing 3DM files. Use a new output version for another run.</p><p><a href="form_fit.json">Fit parameters</a> · <a href="manual_axon_constraints.json">Manual pixel traces</a> · <a href="recovered_paths.json">Recovered paths</a></p><p>The median one-way image-plane residual is about __ERROR__ pixels on the fit drawing. Dense lines can lead to mismatches.</p></details>
<p><small>Use model_run04 and the SOURCE_FORM filenames for this reconstruction.</small></p></main></html>'''
for key,value in {'SLATS':V['slats'],'PINS':V['dowels'],'NODES':V['joints'],'TOTAL':total,'HOLES':V['holes'],'ERROR':round(fit['median_oneway_blue_distance_px'],2)}.items():page=page.replace('__'+key+'__',str(value))
(P/'index.html').write_text(page,encoding='utf-8')
missing=[]
for link in re.findall(r'(?:href|src)="([^"]+)"',page):
 if not link.startswith(('http','#')) and not (P/link).exists():missing.append(link)
assert not missing,missing
(P/'delivery_check.json').write_text(json.dumps({'local_links_missing':missing,'final_model_sha256':ind['files'][0]['sha256'],'all_checks_passed':True,'browser_render_check':'not performed; raster previews visually inspected separately'},indent=2))
print(P/'index.html')
