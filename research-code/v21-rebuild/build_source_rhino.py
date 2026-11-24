# -*- coding: utf-8 -*-
"""Native Rhino construction; no meshes. Isolated process, no original documents modified."""
import os,json,time,traceback,hashlib,math
import Rhino
import Rhino.Geometry as G
import System.Drawing as C
ROOT=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(ROOT,'model_run04')
if not os.path.isdir(OUT):os.makedirs(OUT)
TOL=1e-7
def save(n,x):
    with open(os.path.join(OUT,n),'w') as f:json.dump(x,f,indent=2)
def point(x):return G.Point3d(*x)
def vector(x):return G.Vector3d(*x)
def xyz(p):return [p.X,p.Y,p.Z]
def volume(b):return abs(G.VolumeMassProperties.Compute(b).Volume)
def valid(b):return b is not None and b.IsValid and b.IsSolid
def overlap(a,b):return a.Min.X<=b.Max.X and b.Min.X<=a.Max.X and a.Min.Y<=b.Max.Y and b.Min.Y<=a.Max.Y and a.Min.Z<=b.Max.Z and b.Min.Z<=a.Max.Z
def export(name,parts):
    path=os.path.join(OUT,name)
    if os.path.exists(path):raise RuntimeError('Refuse to overwrite existing 3dm '+name)
    doc=Rhino.FileIO.File3dm();doc.Settings.ModelUnitSystem=getattr(Rhino.UnitSystem,'None');doc.Settings.ModelAbsoluteTolerance=TOL
    doc.ApplicationName='MultiCam V21 source-form interpretation'
    doc.ApplicationDetails='Plan curves from video 33s; height fit to 36s; sections and holes assumed. Not author CAD.'
    layers={};bounds=G.BoundingBox.Empty
    for p in parts:
        key=('TIMBER_'+p['path']) if p['kind']=='slat' else 'DOWELS'
        if key not in layers:
            layer=Rhino.DocObjects.Layer();layer.Name=key
            layer.Color=C.Color.FromArgb(187,145,91) if p['kind']=='slat' else C.Color.FromArgb(28,125,137)
            doc.AllLayers.Add(layer);layers[key]=doc.AllLayers.Count-1
        a=Rhino.DocObjects.ObjectAttributes();a.Name=p['id'];a.LayerIndex=layers[key]
        tags={'status':'SOURCE IMAGE CONSTRAINED INTERPRETATION; NOT AUTHOR CAD','units':'None; 1 model unit = 100 source-plan pixels; no metric calibration','part_kind':p['kind'],'source_path':p.get('path',''),'source_plan':'video 33.000s native frame 1651','source_height':'video 36.000s regularized fit, underconstrained','section_and_holes':'explicit design assumptions in solid_input.json','node_ids':','.join(p.get('nodes',[])),'connected_slats':','.join(p.get('slats',[])),'geometry':'Native closed Brep with Boolean holes; no Mesh objects','fabrication_ready':'false'}
        for k,v in tags.items():a.SetUserString(k,v)
        doc.Objects.AddBrep(p['brep'],a);bounds.Union(p['brep'].GetBoundingBox(True))
    view=Rhino.DocObjects.ViewInfo();view.Name='Source-form overview';vp=view.Viewport;c=bounds.Center;d=bounds.Diagonal.Length
    eye=c+G.Vector3d(-d*.15,-d,d*.9);vp.SetCameraLocation(eye);vp.SetCameraDirection(c-eye);vp.SetCameraUp(G.Vector3d(0,0,1));vp.SetFrustum(-d*.6,d*.6,-d*.42,d*.42,.01,d*10)
    doc.Views.Add(view);doc.NamedViews.Add(view)
    assert doc.Write(path,7)
    back=Rhino.FileIO.File3dm.Read(path);assert back.Objects.Count==len(parts)
    for o in back.Objects:assert isinstance(o.Geometry,G.Brep) and valid(o.Geometry)
    hd=Rhino.RhinoDoc.OpenHeadless(path);assert hd is not None;n=0
    for o in hd.Objects:assert isinstance(o.Geometry,G.Brep) and valid(o.Geometry);n+=1
    hd.Dispose();assert n==len(parts)
    with open(path,'rb') as f:sha=hashlib.sha256(f.read()).hexdigest()
    return {'file':name,'sha256':sha,'valid_closed_breps':len(parts),'mesh_objects':0,'native_headless_readback':'PASS'}
def main():
    start=time.time()
    with open(os.path.join(ROOT,'solid_input.json')) as f:data=json.load(f)
    slats=data['slats'];lookup={};tests=[]
    for s in slats:
        a=point(s['a']);b=point(s['b']);v=b-a;length=v.Length;v.Unitize();r=vector(s['radial']);c=a+(b-a)*.5
        plane=G.Plane(c,v,r);box=G.Box(plane,G.Interval(-length/2,length/2),G.Interval(-s['width']/2,s['width']/2),G.Interval(-s['thickness']/2,s['thickness']/2))
        s['brep']=box.ToBrep();s['stock']=s['brep'].DuplicateBrep();s['bounds']=s['brep'].GetBoundingBox(True);s['kind']='slat';s['holes']=[];s['cutters']=[];s['plane']=plane;s['half']=[length/2,s['width']/2,s['thickness']/2];s['corners']=[xyz(p) for p in box.GetCorners()];lookup[s['id']]=s
        assert valid(s['brep'])
    collisions=[];candidates=0
    for i,a in enumerate(slats):
        for b in slats[i+1:]:
            if not overlap(a['bounds'],b['bounds']):continue
            candidates+=1;pieces=G.Brep.CreateBooleanIntersection(a['brep'],b['brep'],TOL)
            amount=sum(volume(p) for p in pieces) if pieces else 0
            if amount>1e-10:collisions.append({'slats':[a['id'],b['id']],'overlap_volume':amount})
    save('stock_collision.json',{'candidate_pairs':candidates,'collisions':collisions})
    if collisions:raise RuntimeError('Resolve stock overlap before cutting: '+str(len(collisions)))
    dowels=[];pin_axes=[]
    def exit_distance(s,p,v):
        plane=s['plane'];delta=p-plane.Origin;axes=[plane.XAxis,plane.YAxis,plane.ZAxis];ts=[]
        for ax,h in zip(axes,s['half']):
            q=G.Vector3d.Multiply(delta,ax);d=G.Vector3d.Multiply(v,ax)
            if abs(d)>1e-10:
                t=((h if d>0 else -h)-q)/d
                if t>=0:ts.append(t)
        return min(ts)
    for row in data['axes']:
        a=lookup[row['slats'][0]];b=lookup[row['slats'][1]];p=point(row['a']);q=point(row['b']);direction=q-p;length=direction.Length;direction.Unitize()
        exa=exit_distance(a,p,-direction)+row['radius']*.5;exb=exit_distance(b,q,direction)+row['radius']*.5
        p0=p-direction*exa;p1=q+direction*exb
        pin=G.Cylinder(G.Circle(G.Plane(p0,direction),row['radius']),p0.DistanceTo(p1)).ToBrep(True,True)
        cutter=G.Cylinder(G.Circle(G.Plane(p0-direction*.05,direction),row['bore_radius']),p0.DistanceTo(p1)+.1).ToBrep(True,True)
        assert valid(pin)
        dowels.append({'id':row['id'],'kind':'dowel','brep':pin,'slats':row['slats'],'nodes':[row['node']]})
        pin_axes.append({'id':row['id'],'start':xyz(p0),'end':xyz(p1),'radius':row['radius'],'slats':row['slats']})
        for s,pt in [(a,p),(b,q)]:s['cutters'].append(cutter);s['holes'].append(pt)
    for i,s in enumerate(slats):
        b=s['brep'];v0=volume(b)
        for cutter in s['cutters']:
            diff=G.Brep.CreateBooleanDifference(b,cutter,TOL)
            if not diff or len(diff)!=1 or not valid(diff[0]):raise RuntimeError('Hole Boolean failed '+s['id'])
            b=diff[0]
        for p in s['holes']:
            if b.IsPointInside(p,TOL,True):raise RuntimeError('Bore centre not empty '+s['id'])
        chi=b.Vertices.Count-b.Edges.Count+sum(2-f.Loops.Count for f in b.Faces);genus=(2-chi)/2.
        if genus!=len(s['holes']):raise RuntimeError('Merged or open bores '+s['id']+' '+str(genus)+'/'+str(len(s['holes'])))
        s['brep']=b;tests.append({'id':s['id'],'valid':b.IsValid,'solid':b.IsSolid,'holes':len(s['holes']),'genus':genus,'removed_volume':v0-volume(b)})
        if i%20==0:save('progress.json',{'stage':'drilling','done':i,'total':len(slats),'seconds':time.time()-start})
    pin_wood=[];pc=0
    for i,d in enumerate(dowels):
        bb=d['brep'].GetBoundingBox(True)
        for s in slats:
            if not overlap(bb,s['bounds']):continue
            pc+=1;pieces=G.Brep.CreateBooleanIntersection(d['brep'],s['brep'],TOL);amount=sum(volume(p) for p in pieces) if pieces else 0
            if amount>1e-10:pin_wood.append({'pin':d['id'],'wood':s['id'],'assigned':s['id'] in d['slats'],'overlap_volume':amount})
        if i%100==0:save('progress.json',{'stage':'pin-wood collisions','done':i,'total':len(dowels),'seconds':time.time()-start})
    save('pin_wood_collision.json',{'candidate_pairs':pc,'collisions':pin_wood})
    if pin_wood:raise RuntimeError('Resolve pin wood overlaps '+str(len(pin_wood)))
    allparts=slats+dowels
    files=[export('V21_SOURCE_FORM_FULL_CLOSED_BREP.3dm',allparts)]
    # Actual connected node, taken from this full file.
    focus=data['nodes'][len(data['nodes'])//3];ids=set(focus['slats']+focus['dowels']);subset=[p for p in allparts if p['id'] in ids]
    files.append(export('V21_SOURCE_FORM_NODE_CLOSED_BREP.3dm',subset))
    edges=[]
    for p in allparts:
        curves=[]
        for e in p['brep'].Edges:
            n=2 if e.IsLinear(TOL) else 12
            curves.append([xyz(e.PointAt(e.Domain.ParameterAt(k/float(n-1)))) for k in range(n)])
        edges.append({'id':p['id'],'kind':p['kind'],'curves':curves})
    save('native_brep_edges.json',edges);save('hole_validation.json',tests);save('pin_axes.json',pin_axes)
    save('slat_corners.json',[{'id':s['id'],'corners':s['corners']} for s in slats])
    save('validation.json',{'status':'PASS_NATIVE_BREP_CHECKS','files':files,'slats':len(slats),'joints':len(data['nodes']),'dowels':len(dowels),'holes':sum(len(s['holes']) for s in slats),'graph_component_sizes':sorted([len(x) for x in data['graph_components']],reverse=True),'focus_node':focus,'source_exact':False,'metric_scale':None,'fabrication_ready':False,'pin_pin_collision':'pending independent capsule check','native_Rhino_version':str(Rhino.RhinoApp.Version),'seconds':time.time()-start})
    save('progress.json',{'stage':'complete','seconds':time.time()-start})
try:main()
except Exception:save('error.json',{'traceback':traceback.format_exc()})
