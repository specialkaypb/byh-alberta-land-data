import zipfile, struct, sys, gzip, os
Z=zipfile.ZipFile(sys.argv[1]); OUT=sys.argv[2]; P='AGRASID41SHP/'; T='DominantAGRASID_LSRSforQuarterSections'
def hdr(fh):
    h=fh.read(32); nrec=struct.unpack('<I',h[4:8])[0]; hlen=struct.unpack('<H',h[8:10])[0]
    rlen=struct.unpack('<H',h[10:12])[0]; flds=[]; read=32
    while True:
        fd=fh.read(32); read+=32
        if fd[0:1] in (b'\r',b'',b'\x1a'): break
        flds.append((fd[0:11].split(b'\x00')[0].decode('latin-1').strip(), fd[16]))
        if read>=hlen-1: break
    fh.read(max(0,hlen-read)); return nrec,rlen,flds
fd=Z.open(P+T+'.dbf'); n,rl,flds=hdr(fd)
fs=Z.open(P+T+'.shp'); fs.read(100)
g=gzip.open(os.path.join(OUT,'qs_lsrs.tsv.gz'),'wt',encoding='utf-8',newline='',compresslevel=9)
g.write('parcel\tmer\trge\ttwp\tsec\tqs\tlsrs\tgeom\n')
def num(s):
    try: return str(int(float(s)))
    except: return ''
c=0
for _ in range(n):
    rec=fd.read(rl)
    if len(rec)<rl: break
    o=1; d={}
    for nm,ln in flds: d[nm]=rec[o:o+ln].decode('latin-1').strip(); o+=ln
    h=fs.read(8)
    if len(h)<8: break
    cb=fs.read(struct.unpack('>i',h[4:8])[0]*2)
    if struct.unpack('<i',cb[0:4])[0]==0: continue
    np_=struct.unpack('<i',cb[36:40])[0]; npt=struct.unpack('<i',cb[40:44])[0]
    po=44+4*np_; pts=struct.unpack('<%dd'%(npt*2), cb[po:po+16*npt])
    ring=' '.join('%.0f,%.0f'%(pts[j],pts[j+1]) for j in range(0,len(pts),2))
    g.write('\t'.join([d['PARCEL_ID'],num(d['M']),num(d['RGE']),num(d['TWP']),num(d['SEC']),
                       d['QS'],num(d['Dom_LSRS']),ring])+'\n'); c+=1
g.close()
sys.stderr.write('quarter sections: %d -> %.1f MB\n'%(c,os.path.getsize(os.path.join(OUT,'qs_lsrs.tsv.gz'))/1e6))
