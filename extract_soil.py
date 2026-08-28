import zipfile, struct, sys, gzip, os, collections

Z = zipfile.ZipFile(sys.argv[1]); OUT = sys.argv[2]; P = 'AGRASID41SHP/'

def hdr(fh):
    h=fh.read(32); nrec=struct.unpack('<I',h[4:8])[0]; hlen=struct.unpack('<H',h[8:10])[0]
    rlen=struct.unpack('<H',h[10:12])[0]; flds=[]; read=32
    while True:
        fd=fh.read(32); read+=32
        if fd[0:1] in (b'\r',b'',b'\x1a'): break
        flds.append((fd[0:11].split(b'\x00')[0].decode('latin-1').strip(), fd[16]))
        if read>=hlen-1: break
    fh.read(max(0,hlen-read)); return nrec,rlen,flds

def rows(t):
    fh=Z.open(P+t+'.dbf'); n,rl,f=hdr(fh)
    for _ in range(n):
        rec=fh.read(rl)
        if len(rec)<rl: break
        o=1; d={}
        for nm,ln in f: d[nm]=rec[o:o+ln].decode('cp1252','replace').strip(); o+=ln
        yield d

def shapes(t):
    fh=Z.open(P+t+'.shp'); fh.read(100)
    while True:
        h=fh.read(8)
        if len(h)<8: break
        c=fh.read(struct.unpack('>i',h[4:8])[0]*2)
        st=struct.unpack('<i',c[0:4])[0]
        if st==0: yield None; continue
        np_=struct.unpack('<i',c[36:40])[0]; npt=struct.unpack('<i',c[40:44])[0]
        po=44; parts=list(struct.unpack('<%di'%np_, c[po:po+4*np_])); po+=4*np_
        pts=struct.unpack('<%dd'%(npt*2), c[po:po+16*npt])
        yield parts, pts

def ring_text(parts, pts, prec=1):
    parts = list(parts)+[len(pts)//2]; out=[]
    for i in range(len(parts)-1):
        s=pts[parts[i]*2:parts[i+1]*2]
        if len(s)<8: continue
        out.append(' '.join('%.*f,%.*f'%(prec,s[j],prec,s[j+1]) for j in range(0,len(s),2)))
    return ';'.join(out)

sys.stderr.write('indexing lookup tables...\n')
names = {r['SOIL_ID']: r for r in rows('SoilNames')}
lsrs  = {r['POLY_ID']: r for r in rows('LandSuitabilityRatings')}
lform = {r['LCODE']: r for r in rows('Landforms')}
prof  = {}
for r in rows('SoilProfiles'):
    if r.get('Primary_') == '1' or r['CMP_ID'] not in prof:
        prof[r['CMP_ID']] = r['SOIL_ID']
comp = collections.defaultdict(list)
for r in rows('PolygonComponents'):
    comp[r['POLY_ID']].append(r)
sys.stderr.write('  soils %d, lsrs %d, landforms %d, profiles %d, polys with components %d\n'
                 % (len(names), len(lsrs), len(lform), len(prof), len(comp)))

COLS = ['poly_id','muname','landform','lcode','slope_pct','slope_len','stoniness','lfpos','cmp_pct',
        'lsrs_grain','lsrs_alfalfa','lsrs_brome','lsrs_canola','soilname','soil_id','drainage',
        'salinity','calcar','kind','watertbl','rootrestr','pm_tex','pm_type','order3','ggroup3',
        'sgroup3','report','geom']
g = gzip.open(os.path.join(OUT,'soil_polygons.tsv.gz'),'wt',encoding='utf-8',newline='',compresslevel=9)
g.write('\t'.join(COLS)+'\n')
n=0
for poly, shp in zip(rows('SoilLandscapePolygons'), shapes('SoilLandscapePolygons')):
    if shp is None: continue
    pid=poly['POLY_ID']
    cs=sorted(comp.get(pid,[]), key=lambda r:-float(r['PERCENT_'] or 0))
    c=cs[0] if cs else {}
    sid=prof.get(c.get('CMP_ID',''),'')
    s=names.get(sid,{})
    lf=lform.get(poly['LCODE'],{})
    L=lsrs.get(pid,{})
    row=[pid, poly['MUNAME'], lf.get('NAME',''), poly['LCODE'],
         c.get('SLOPE_P',''), c.get('SLOPE_LEN',''), c.get('STONINESS',''), c.get('LFPOS',''),
         c.get('PERCENT_',''),
         L.get('SSSGRAIN',''), L.get('Alfalfa',''), L.get('Brome',''), L.get('Canola',''),
         s.get('SOILNAME',''), sid, s.get('DRAINAGE',''), s.get('SALINITY',''), s.get('CALCAR',''),
         s.get('KIND',''), s.get('WATERTBL',''), s.get('ROOTRESTRI',''), s.get('PM1_TEX',''),
         s.get('PM1_TYP',''), s.get('ORDER3',''), s.get('G_GROUP3',''), s.get('S_GROUP3',''),
         s.get('REPORT',''), ring_text(shp[0], shp[1])]
    g.write('\t'.join(str(x).replace('\t',' ').replace('\n',' ') for x in row)+'\n'); n+=1
g.close()
sys.stderr.write('soil polygons: %d -> %.1f MB\n' % (n, os.path.getsize(os.path.join(OUT,'soil_polygons.tsv.gz'))/1e6))
