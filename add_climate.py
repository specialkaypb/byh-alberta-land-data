#!/usr/bin/env python3
"""
Add the ACIS climate layer to an existing data pack.

Climate is written to its own directory rather than merged into the tiles.
Tiles are gzipped blobs, so merging would make git store a fresh 86 MB copy of
every tile on every climate refresh. Separate files mean a refresh touches only
what changed, and the AER, soil and water layers are never rewritten.

    pack/
      tiles/<r>_<c>.tsv.gz        wells, pipes, soil, water        unchanged
      climate/<r>_<c>.tsv.gz      one row per township             new
      acis_stations.json.gz       536 station normals              new

Usage:
    python3 add_climate.py PACKDIR townships.jsonl extremes.json centres.json [stations.json]
"""
import gzip
import json
import os
import sys

PACK, TWP, EXT, CEN = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
STN = sys.argv[5] if len(sys.argv) > 5 else ''

man = json.load(open(os.path.join(PACK, 'manifest.json')))
LAT0, LON0 = man['grid']['lat0'], man['grid']['lon0']
DLAT, DLON = man['grid']['dlat'], man['grid']['dlon']

COLS = ['twp', 'lat', 'lon', 'ata', 'atasd', 'atvn', 'atvx', 'ath', 'athrec',
        'atl', 'atlrec', 'prcip', 'prcipsd', 'swemx', 'wsa', 'irt', 'irmt', 'n',
        'minmean', 'maxmean']


def cell(lat, lon):
    return int((lat - LAT0) / DLAT), int((lon - LON0) / DLON)


def fmt(v):
    return '' if not v else ','.join('' if x is None else ('%g' % x) for x in v)


def one(v):
    return '' if v is None else '%g' % v


# Undo any earlier in-tile merge, so a pack built by a previous version of this
# script comes out clean rather than carrying the layer twice.
stripped = 0
for fn in sorted(os.listdir(os.path.join(PACK, 'tiles'))):
    p = os.path.join(PACK, 'tiles', fn)
    raw = gzip.decompress(open(p, 'rb').read()).decode('utf-8')
    if '#LAYER climate' not in raw:
        continue
    keep, skip = [], False
    for line in raw.split('\n'):
        if line.startswith('#LAYER '):
            skip = line[7:].strip() == 'climate'
        if not skip and line:
            keep.append(line)
    with gzip.open(p, 'wt', encoding='utf-8', compresslevel=9) as fh:
        fh.write('\n'.join(keep) + '\n')
    key = fn[:-7]
    if key in man['tiles']:
        man['tiles'][key]['bytes'] = os.path.getsize(p)
        man['tiles'][key].get('counts', {}).pop('climate', None)
    stripped += 1
if stripped:
    print('stripped an earlier in-tile climate layer from %d tiles' % stripped)

cen = json.load(open(CEN))
ext = json.load(open(EXT)) if EXT and os.path.exists(EXT) else {}
print('township centres: %d, annual extremes: %d' % (len(cen), len(ext)))

rows = {}
n = miss = noext = 0
for line in open(TWP, encoding='utf-8'):
    line = line.strip()
    if not line:
        continue
    rec = json.loads(line)
    code, d = rec['t'], rec['d']
    try:
        mer, rge, twp = int(code[8]), int(code[5:7]), int(code[1:4])
    except Exception:
        miss += 1
        continue
    c = cen.get('%d,%d,%d' % (mer, rge, twp))
    if not c:
        miss += 1
        continue
    lat, lon = c[0], c[1]
    g = lambda k, f='m': (d.get(k) or {}).get(f)
    yrs = max([(d.get(k) or {}).get('n', 0) for k in d] or [0])
    e = ext.get(code) or {}
    if e.get('minMean') is None:
        noext += 1
    rows.setdefault(cell(lat, lon), []).append('\t'.join([
        code, '%.5f' % lat, '%.5f' % lon,
        fmt(g('ATA')), fmt(g('ATA', 'sd')), fmt(g('ATVN')), fmt(g('ATVX')),
        fmt(g('ATH')), one(g('ATH', 'rec')), fmt(g('ATL')), one(g('ATL', 'rec')),
        fmt(g('PRCIP')), fmt(g('PRCIP', 'sd')), fmt(g('SWEMX')),
        fmt(g('WSA')), fmt(g('IRT')), fmt(g('IRMT')), str(yrs),
        one(e.get('minMean')), one(e.get('maxMean'))]))
    n += 1
print('climate rows: %d placed, %d without a township centre, %d without annual extremes'
      % (n, miss, noext))

os.makedirs(os.path.join(PACK, 'climate'), exist_ok=True)
man['climate_tiles'] = {}
tot = 0
for (r, c), body in sorted(rows.items()):
    key = '%d_%d' % (r, c)
    p = os.path.join(PACK, 'climate', '%s.tsv.gz' % key)
    with gzip.open(p, 'wt', encoding='utf-8', compresslevel=9) as fh:
        fh.write('#COLS %s\n' % '\t'.join(COLS))
        fh.write('\n'.join(body) + '\n')
    sz = os.path.getsize(p)
    tot += sz
    man['climate_tiles'][key] = {'bytes': sz, 'townships': len(body)}

man['cols']['climate'] = COLS
if 'Alberta Climate Information Service' not in man.get('source', ''):
    man['source'] = man.get('source', '') + ('; Alberta Climate Information Service (ACIS), '
                                             'Alberta Agriculture and Irrigation')
man['climate'] = {
    'township_window': '1996 to 2025',
    'station_window': '1991 to 2020',
    'townships': n,
    'stations': 0,
    'gaps': [
        '73 townships in the far northeast, township 117 to 126 range 16 to 23 west of the '
        '4th meridian, return no interpolated series at all. That corner is largely Wood '
        'Buffalo National Park.',
        '83 townships publish monthly values but no yearly extremes, so their hardiness '
        'figure falls back to the coldest month average and is labelled approximate.',
        '26 of the 562 stations have no 1991 to 2020 normals and were dropped. They are the '
        'mountain park stations, one out of province station, and stations commissioned '
        'after 2023. There are no station normals inside the mountain parks.',
        'Prevailing wind direction is published daily only, never as a normal, so it is not '
        'carried here.',
    ]}

if STN and os.path.exists(STN):
    blob = json.load(open(STN, encoding='utf-8'))
    man['climate']['stations'] = len(blob.get('normals', {}))
    with gzip.open(os.path.join(PACK, 'acis_stations.json.gz'), 'wt',
                   encoding='utf-8', compresslevel=9) as fh:
        json.dump(blob, fh, separators=(',', ':'))
    sz = os.path.getsize(os.path.join(PACK, 'acis_stations.json.gz'))
    print('station normals: %d stations, %.2f MB' % (man['climate']['stations'], sz / 1e6))

json.dump(man, open(os.path.join(PACK, 'manifest.json'), 'w'), indent=1)
print('%d climate files, %.2f MB total' % (len(rows), tot / 1e6))
