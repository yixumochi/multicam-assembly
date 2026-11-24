# -*- coding: utf-8 -*-
import os,json,traceback
import Rhino
import Rhino.Geometry as G
ROOT=os.path.dirname(os.path.abspath(__file__));OUT=os.path.join(ROOT,'model_run04')
def xyz(p):return [p.X,p.Y,p.Z]
try:
    doc=Rhino.FileIO.File3dm.Read(os.path.join(OUT,'V21_SOURCE_FORM_FULL_CLOSED_BREP.3dm'));rows=[];counts=0
    for o in doc.Objects:
        g=o.Geometry
        assert isinstance(g,G.Brep) and g.IsValid and g.IsSolid
        counts+=1
        if o.Attributes.GetUserString('part_kind')!='slat':continue
        for face in g.Faces:
            if not face.IsPlanar(1e-7):continue
            normal=face.NormalAt(face.Domain(0).Mid,face.Domain(1).Mid)
            loops=[]
            for loop in face.Loops:
                c=loop.To3dCurve();segs=c.DuplicateSegments()
                if not segs:segs=[c]
                points=[]
                for e in segs:
                    n=2 if e.IsLinear(1e-7) else 16
                    points.extend([xyz(e.PointAt(e.Domain.ParameterAt(k/float(n-1)))) for k in range(n)])
                loops.append(points)
            rows.append({'id':o.Attributes.Name,'normal':xyz(normal),'loops':loops})
    with open(os.path.join(OUT,'native_brep_faces.json'),'w') as f:json.dump(rows,f)
    with open(os.path.join(OUT,'face_export_receipt.json'),'w') as f:json.dump({'closed_breps_read':counts,'planar_faces_exported':len(rows),'method':'Native Brep face loops, cylindrical bores excluded from face fill; no Mesh objects or mesh conversion','source_file_unchanged':True},f,indent=2)
except Exception:
    with open(os.path.join(OUT,'face_error.json'),'w') as f:json.dump({'traceback':traceback.format_exc()},f)
