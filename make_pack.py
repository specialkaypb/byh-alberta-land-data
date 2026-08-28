#!/usr/bin/env python3
"""
Tile the AER layers into a grid of self-contained data tiles for the map skill.

Each tile is one gzipped text file holding every layer for that cell, in sections:
    #LAYER wells
    #COLS a\tb\tc
    <rows>
    #LAYER pipes
    ...
A build fetches only the cells its query circle touches.
"""
import gzip, json, math, os, sys, collections
import pyproj

SRC = sys.argv[1]
OUT = sys.argv[2]
LAT0, LON0 = 48.9, -120.4
DLAT, DLON = 1.1, 2.0
os.makedirs(os.path.join(OUT, 'tiles'), exist_ok=True)


def cell(lat, lon):
    return int((lat - LAT0) / DLAT), int((lon - LON0) / DLON)


def tsv(path):
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        hdr = fh.readline().rstrip('\n').split('\t')
        for line in fh:
            p = line.rstrip('\n').split('\t')
            if len(p) < len(hdr):
                p += [''] * (len(hdr) - len(p))
            yield dict(zip(hdr, p))


def clean(v):
    return (v or '').replace('\t', ' ').replace('\n', ' ').replace('\r', '')


BUCKETS = collections.defaultdict(lambda: collections.defaultdict(list))
COLS = {}


def add(layer, r, c, row):
    BUCKETS[(r, c)][layer].append('\t'.join(clean(x) for x in row))


# ------------------------------------------------------------------ wells --
print('indexing bottom holes and abandoned records...')
bh = {}
for r in tsv(os.path.join(SRC, 'wells_bottom.tsv.gz')):
    k = r['Well_Lic']
    if k not in bh:
        bh[k] = (r.get('Well_UWI', ''), r.get('Well_Name', ''), r.get('Max_TVD', ''),
                 r.get('Fin_Total', ''), r.get('BH_Latitud', ''), r.get('BH_Longitu', ''))
ab = {}
for r in tsv(os.path.join(SRC, 'abandoned.tsv.gz')):
    ab[r['Licence']] = (r.get('SurfLoc', ''), r.get('Fluid', ''), r.get('Phone', ''), r.get('City', ''))
rev = {}
for r in tsv(os.path.join(SRC, 'revised_abnd.tsv.gz')):
    rev[r['Licence_No']] = (r.get('SH_Rev_Lat', ''), r.get('SH_Rev_Lon', ''))

COLS['wells'] = ['lic', 'licensee', 'status', 'statusdate', 'elev', 'spud', 'findrill', 'edct',
                 'lat', 'lon', 'uwi', 'wellname', 'tvd', 'ftot', 'blat', 'blon', 'lsd', 'fluid',
                 'phone', 'city', 'revlat', 'revlon']
n = 0
for r in tsv(os.path.join(SRC, 'wells_surface.tsv.gz')):
    try:
        lat, lon = float(r['SH_Lat']), float(r['SH_Long'])
    except Exception:
        continue
    if not (48.5 < lat < 60.6 and -121 < lon < -109):
        continue
    lic = r['Well_Lic']
    b = bh.get(lic, ('', '', '', '', '', ''))
    a = ab.get(lic, ('', '', '', ''))
    v = rev.get(lic, ('', ''))
    rr, cc = cell(lat, lon)
    add('wells', rr, cc, [lic, r.get('Licensee', ''), r.get('Lic_Status', ''), r.get('Status_Dat', ''),
                          r.get('Ground_Ele', ''), r.get('Spud_Date', ''), r.get('Fin_Drill', ''),
                          r.get('EDCT', ''), '%.6f' % lat, '%.6f' % lon,
                          b[0], b[1], b[2], b[3], b[4], b[5], a[0], a[1], a[2], a[3], v[0], v[1]])
    n += 1
print('  wells tiled:', n)
del bh, ab

# -------------------------------------------------------------- pipelines --
COLS['pipes'] = ['licence', 'line', 'company', 'segstatus', 'sub1', 'sub2', 'h2s', 'h2slvl', 'od',
                 'wall', 'material', 'maop', 'frm', 'to', 'seglen', 'approved', 'geom']
n = 0
for r in tsv(os.path.join(SRC, 'pipelines.tsv.gz')):
    g = r.get('geom', '')
    if not g:
        continue
    base = [r.get('LICENCE_NO', ''), r.get('LINE_NO', ''), r.get('COMP_NAME', ''),
            r.get('SEG_STATUS', ''), r.get('SUBSTANCE1', ''), r.get('SUBSTANCE2', ''),
            r.get('H2S_CONT', ''), r.get('H2S_R_LEVL', ''), r.get('OUT_DIAMET', ''),
            r.get('WALL_THICK', ''), r.get('PIP_MATERL', ''), r.get('PIPE_MAOP', ''),
            r.get('FROM_LOC', ''), r.get('TO_LOC', ''), r.get('SEG_LENGTH', ''),
            r.get('LICAPPDATE', '')]
    for seg in g.split(';'):
        pts = [c for c in seg.split(' ') if ',' in c]
        if len(pts) < 2:
            continue
        xs, ys = [], []
        for c in pts:
            x, y = c.split(',')
            xs.append(float(x)); ys.append(float(y))
        if not (48.5 < min(ys) and max(ys) < 60.6 and -121 < min(xs) and max(xs) < -109):
            continue
        r0, c0 = cell(min(ys), min(xs))
        r1, c1 = cell(max(ys), max(xs))
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                add('pipes', rr, cc, base + [seg])
        n += 1
print('  pipeline parts tiled:', n)

# ------------------------------------------------ facilities, installs, rev --
COLS['fac'] = ['facid', 'facname', 'operator', 'subty', 'licnum', 'licensee', 'status', 'edct',
               'locsrc', 'lat', 'lon']
n = 0
for r in tsv(os.path.join(SRC, 'facilities.tsv.gz')):
    g = r.get('geom', '')
    if ',' not in g:
        continue
    lon, lat = [float(v) for v in g.split(',')]
    if not (48.5 < lat < 60.6 and -121 < lon < -109):
        continue
    rr, cc = cell(lat, lon)
    add('fac', rr, cc, [r.get('FAC_ID', ''), r.get('FAC_NAME', ''), r.get('OPERATOR', ''),
                        r.get('FAC_SUB_TY', ''), r.get('LIC_NUMBER', ''), r.get('LICENSEE', ''),
                        r.get('FAC_STATUS', ''), r.get('EDCT_DESCR', ''), r.get('LOC_SOURCE', ''),
                        '%.6f' % lat, '%.6f' % lon])
    n += 1
print('  facilities tiled:', n)

COLS['inst'] = ['licinstno', 'type', 'company', 'status', 'h2s', 'sub1', 'sub2', 'loc', 'fldctr',
                'power', 'prime', 'lat', 'lon']
n = 0
for r in tsv(os.path.join(SRC, 'installations.tsv.gz')):
    g = r.get('geom', '')
    if ',' not in g:
        continue
    lon, lat = [float(v) for v in g.split(',')]
    if not (48.5 < lat < 60.6 and -121 < lon < -109):
        continue
    rr, cc = cell(lat, lon)
    add('inst', rr, cc, [r.get('LICINSTNO', ''), r.get('INSTA_TYPE', ''), r.get('BA_NAME', ''),
                         r.get('PLINSTATUS', ''), r.get('H2S_CONT', ''), r.get('SUBSTANCE1', ''),
                         r.get('SUBSTANCE2', ''), r.get('INST_LOCAT', ''), r.get('FLD_CENTRE', ''),
                         r.get('POWER', ''), r.get('PRIME_SORC', ''), '%.6f' % lat, '%.6f' % lon])
    n += 1
print('  installations tiled:', n)

COLS['rev'] = ['licence', 'lat', 'lon']
n = 0
for r in tsv(os.path.join(SRC, 'revised_abnd.tsv.gz')):
    try:
        lat, lon = float(r['SH_Rev_Lat']), float(r['SH_Rev_Lon'])
    except Exception:
        continue
    rr, cc = cell(lat, lon)
    add('rev', rr, cc, [r.get('Licence_No', ''), '%.6f' % lat, '%.6f' % lon])
    n += 1
print('  revised locations tiled:', n)


# ----------------------------------------------------------------- soil ---
# AGRASID ships in NAD83 10TM AEP Forest. Reproject here so the skill stays
# stdlib-only, and simplify: 1:100,000 polygons carry far more vertices than a
# property map can use.
SOIL_SRC = os.environ.get('BYH_SOIL_SRC', '')
if SOIL_SRC and os.path.exists(os.path.join(SOIL_SRC, 'soil_polygons.tsv.gz')):
    _tm = pyproj.CRS.from_proj4('+proj=tmerc +lat_0=0 +lon_0=-115 +k=0.9992 +x_0=500000 '
                                '+y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs')
    _tr = pyproj.Transformer.from_crs(_tm, 'EPSG:4326', always_xy=True)
    sys.setrecursionlimit(30000)

    def _dp(pts, tol):
        if len(pts) < 3:
            return pts
        x0, y0 = pts[0]; x1, y1 = pts[-1]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        worst, wi = -1.0, 0
        for i in range(1, len(pts) - 1):
            px, py = pts[i]
            d = (abs(dy * px - dx * py + x1 * y0 - y1 * x0) / L) if L > 1e-9 else math.hypot(px - x0, py - y0)
            if d > worst:
                worst, wi = d, i
        if worst <= tol:
            return [pts[0], pts[-1]]
        return _dp(pts[:wi + 1], tol)[:-1] + _dp(pts[wi:], tol)

    COLS['soil'] = ['muname', 'soilname', 'order', 'landform', 'slope', 'drain', 'salt', 'calc',
                    'tex', 'grain', 'alfalfa', 'brome', 'canola', 'pct', 'report', 'geom']
    n = 0
    for r in tsv(os.path.join(SOIL_SRC, 'soil_polygons.tsv.gz')):
        out_rings = []
        for seg in r['geom'].split(';'):
            pts = []
            for c in seg.split(' '):
                if ',' in c:
                    a, b = c.split(','); pts.append((float(a), float(b)))
            if len(pts) < 4:
                continue
            simp = _dp(pts, 20.0)
            if len(simp) < 4:
                simp = pts
            xs, ys = zip(*simp)
            lons, lats = _tr.transform(xs, ys)
            out_rings.append(' '.join('%.5f,%.5f' % (lo, la) for lo, la in zip(lons, lats)))
        if not out_rings:
            continue
        base = [r['muname'], r['soilname'].title(), r['order3'], r['landform'],
                r['slope_pct'], r['drainage'], r['salinity'], r['calcar'], r['pm_tex'],
                r['lsrs_grain'], r['lsrs_alfalfa'], r['lsrs_brome'], r['lsrs_canola'],
                r['cmp_pct'], r['report']]
        for ring in out_rings:
            cd = [tuple(float(v) for v in c.split(',')) for c in ring.split(' ')]
            la = [q[1] for q in cd]; lo = [q[0] for q in cd]
            if not (48.5 < min(la) and max(la) < 60.6 and -121 < min(lo) and max(lo) < -109):
                continue
            r0, c0 = cell(min(la), min(lo))
            r1, c1 = cell(max(la), max(lo))
            for rr in range(r0, r1 + 1):
                for cc in range(c0, c1 + 1):
                    add('soil', rr, cc, base + [ring])
            n += 1
    print('  soil polygons tiled:', n)

    # Quarter-section capability is a lookup, not a map layer. Keyed by legal land
    # description, so it answers "what class is NE-14-32-5-W5" exactly and costs almost nothing.
    qp = os.path.join(SOIL_SRC, 'qs_lsrs.tsv.gz')
    if os.path.exists(qp):
        out = gzip.open(os.path.join(OUT, 'qs_lsrs.tsv.gz'), 'wt', encoding='utf-8', compresslevel=9)
        out.write('parcel\tlsrs\n')
        m = 0
        for r in tsv(qp):
            if r.get('lsrs') and r['lsrs'] != '0':
                out.write('%s\t%s\n' % (r['parcel'], r['lsrs'])); m += 1
        out.close()
        print('  quarter-section capability lookup:', m,
              '-> %.1f MB' % (os.path.getsize(os.path.join(OUT, 'qs_lsrs.tsv.gz')) / 1e6))

# ---------------------------------------------------------------- water ---
# One row per water well, already joined out of the AWWID Access database.
# Owner names and addresses are deliberately absent: they are personal
# information and the Open Government Licence does not grant the right to
# redistribute them.
WATER_SRC = os.environ.get('BYH_WATER_SRC', '')
if WATER_SRC and os.path.exists(os.path.join(WATER_SRC, 'water_wells.tsv.gz')):
    COLS['water'] = ['gic', 'lat', 'lon', 'elev', 'legal', 'locsrc', 'use', 'work', 'decom',
                     'drilled', 'depth', 'casing', 'rate', 'intake', 'swl', 'swldatum',
                     'testrate', 'testtype', 'artesian', 'saline', 'gas', 'method',
                     'driller', 'aquifer', 'log']
    n = 0
    for r in tsv(os.path.join(WATER_SRC, 'water_wells.tsv.gz')):
        try:
            lat, lon = float(r['lat']), float(r['lon'])
        except Exception:
            continue
        if not (48.5 < lat < 60.6 and -121 < lon < -109):
            continue
        rr, cc = cell(lat, lon)
        add('water', rr, cc, [r.get(k, '') for k in COLS['water']])
        n += 1
    print('  water wells tiled:', n)


# ------------------------------------------------------------ ATS index ---
# Section and township centres, built once from recorded well locations so a
# legal land description resolves without a geocoder. Carried through on every
# rebuild rather than regenerated, since the survey grid does not move.
ATS = os.environ.get('BYH_ATS_INDEX', '')
if ATS and os.path.exists(ATS):
    with open(ATS, 'rb') as _f, gzip.open(os.path.join(OUT, 'ats_index.json.gz'), 'wb',
                                          compresslevel=9) as _g:
        _g.write(_f.read())
    print('  ATS index copied: %.1f MB'
          % (os.path.getsize(os.path.join(OUT, 'ats_index.json.gz')) / 1e6))


# ----------------------------------------------------------------- write ---
manifest = {'version': '2026-08-28',
            'source': 'Alberta Energy Regulator public spatial data (ST37, ST102, Enhanced Pipeline, '
                      'Abandoned Well Map, Revised Abandoned Well Locations); AGRASID 4.1 soil '
                      'landscapes (Alberta Agriculture and Irrigation with Agriculture and Agri-Food '
                      'Canada); Government of Alberta, Alberta Water Well Information Database',
            'grid': {'lat0': LAT0, 'lon0': LON0, 'dlat': DLAT, 'dlon': DLON},
            'cols': COLS, 'tiles': {}}
sizes = []
for (rr, cc), layers in sorted(BUCKETS.items()):
    key = '%d_%d' % (rr, cc)
    body = []
    counts = {}
    for lyr in ['wells', 'pipes', 'fac', 'inst', 'rev', 'soil', 'water']:
        rows = layers.get(lyr)
        if not rows:
            continue
        counts[lyr] = len(rows)
        body.append('#LAYER %s' % lyr)
        body.append('#COLS %s' % '\t'.join(COLS[lyr]))
        body.extend(rows)
    if not body:
        continue
    p = os.path.join(OUT, 'tiles', '%s.tsv.gz' % key)
    with gzip.open(p, 'wt', encoding='utf-8', compresslevel=9) as fh:
        fh.write('\n'.join(body) + '\n')
    sz = os.path.getsize(p)
    sizes.append((sz, key, counts))
    manifest['tiles'][key] = {'bytes': sz, 'counts': counts}

json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
sizes.sort(reverse=True)
tot = sum(s for s, _, _ in sizes)
print('\n%d tiles, %.1f MB total, largest %.1f MB, median %.2f MB'
      % (len(sizes), tot / 1e6, sizes[0][0] / 1e6, sizes[len(sizes) // 2][0] / 1e6))
for s, k, c in sizes[:6]:
    print('  %-8s %6.2f MB  %s' % (k, s / 1e6, c))
