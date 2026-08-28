import zipfile, struct, sys, gzip, io, os

def dbf_header(f):
    h = f.read(32)
    nrec, hlen, rlen = struct.unpack('<I', h[4:8])[0], struct.unpack('<H', h[8:10])[0], struct.unpack('<H', h[10:12])[0]
    fields = []
    read = 32
    while True:
        fd = f.read(32); read += 32
        if fd[0:1] in (b'\r', b'', b'\x1a'): break
        name = fd[0:11].split(b'\x00')[0].decode('cp1252',errors='replace').strip()
        typ = fd[11:12].decode('cp1252',errors='replace'); ln = fd[16]; dec = fd[17]
        fields.append((name, typ, ln, dec))
        if read >= hlen - 1: break
    f.read(max(0, hlen - read))
    return nrec, rlen, fields

def dbf_rows(f, nrec, rlen, fields, want):
    idx = []; off = 1
    for (name, typ, ln, dec) in fields:
        if name in want: idx.append((name, off, ln, typ))
        off += ln
    for _ in range(nrec):
        rec = f.read(rlen)
        if len(rec) < rlen: break
        yield {n: rec[o:o+l].decode('cp1252',errors='replace').strip() for (n, o, l, t) in idx}

def shp_shapes(f):
    f.read(100)
    while True:
        hd = f.read(8)
        if len(hd) < 8: break
        clen = struct.unpack('>i', hd[4:8])[0] * 2
        c = f.read(clen)
        if len(c) < clen: break
        st = struct.unpack('<i', c[0:4])[0]
        if st == 0: yield None
        elif st == 1 or st == 11 or st == 21:
            x, y = struct.unpack('<dd', c[4:20]); yield ('P', x, y)
        elif st in (3, 5, 13, 15, 23, 25):
            np_ = struct.unpack('<i', c[36:40])[0]; npt = struct.unpack('<i', c[40:44])[0]
            po = 44; parts = list(struct.unpack('<%di' % np_, c[po:po+4*np_])); po += 4*np_
            pts = struct.unpack('<%dd' % (npt*2), c[po:po+16*npt])
            yield ('L', parts, pts)
        else: yield None

def run(zippath, member_base, want, out, prec=6):
    z = zipfile.ZipFile(zippath)
    names = z.namelist()
    shp = next(n for n in names if n.lower().endswith('.shp') and member_base.lower() in n.lower())
    dbf = shp[:-4] + '.dbf'
    if dbf not in names: dbf = next(n for n in names if n.lower() == shp[:-4].lower() + '.dbf')
    fd = z.open(dbf); nrec, rlen, fields = dbf_header(fd)
    sys.stderr.write('records=%d fields=%s\n' % (nrec, [f[0] for f in fields]))
    fs = z.open(shp)
    cols = list(want)
    gz = gzip.open(out, 'wt', encoding='utf-8', newline='')
    gz.write('\t'.join(cols + ['geom']) + '\n')
    n = 0
    for row, shape in zip(dbf_rows(fd, nrec, rlen, fields, set(want)), shp_shapes(fs)):
        if shape is None: continue
        if shape[0] == 'P':
            g = '%.*f,%.*f' % (prec, shape[1], prec, shape[2])
        else:
            _, parts, pts = shape
            segs = []; parts = parts + [len(pts)//2]
            for i in range(len(parts)-1):
                seg = pts[parts[i]*2:parts[i+1]*2]
                segs.append(' '.join('%.*f,%.*f' % (prec, seg[j], prec, seg[j+1]) for j in range(0, len(seg), 2)))
            g = ';'.join(segs)
        gz.write('\t'.join([row.get(c, '').replace('\t', ' ').replace('\n', ' ') for c in cols] + [g]) + '\n')
        n += 1
    gz.close()
    sys.stderr.write('wrote %d -> %s (%d bytes)\n' % (n, out, os.path.getsize(out)))

if __name__ == '__main__':
    zp, mb, o = sys.argv[1], sys.argv[2], sys.argv[3]
    prec = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    want = sys.argv[5].split(',') if len(sys.argv) > 5 else None
    if want is None:
        z = zipfile.ZipFile(zp); names = z.namelist()
        shp = next(n for n in names if n.lower().endswith('.shp') and mb.lower() in n.lower())
        fd = z.open(shp[:-4] + '.dbf'); nrec, rlen, fields = dbf_header(fd)
        print('RECORDS', nrec); print('FIELDS', [(f[0], f[1], f[2]) for f in fields]); sys.exit(0)
    run(zp, mb, want, o, prec)
