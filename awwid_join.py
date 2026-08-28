"""Join the extracted AWWID tables into one row per water well.

Everything in AWWID is imperial (the data dictionary says so on page one), so
depths are feet, rates are imperial gallons per minute and diameters are inches.
Conversion to metric happens in the map builder, not here, so the pack keeps the
source values.

Well_Owners is never read. Owner names and addresses are personal information
and the Open Government Licence does not grant the right to redistribute them.
"""
import gzip, os, subprocess, sys, collections

OUT = '/tmp/byhw/out'
FIN = '/tmp/byhw/water_wells.tsv.gz'


HEADERS = {'Drilling_Companies': ['Drilling_Company_ID', 'Company_Name', 'City', 'Province']}


def rows(name):
    """Yield dicts from the two part files, using the header from part 0."""
    hdr = HEADERS.get(name)
    p0 = os.path.join(OUT, '%s.0.tsv' % name)
    p1 = os.path.join(OUT, '%s.1.tsv' % name)
    for p in (p0, p1):
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            first = True
            for line in fh:
                f = line.rstrip('\n').split('\t')
                if first:
                    first = False
                    if p == p0 and name not in HEADERS:
                        hdr = f
                        continue
                    if hdr and f and f[0] == hdr[0]:
                        continue
                if hdr is None:
                    continue
                if len(f) < len(hdr):
                    f += [''] * (len(hdr) - len(f))
                yield dict(zip(hdr, f))


def dec(s, scale):
    """The extractor wrote every 17 byte decimal at scale 8, which only places a
    dot. Recover the stored integer and apply the column's declared scale."""
    if not s:
        return None
    try:
        return int(s.replace('.', '')) / (10.0 ** scale)
    except ValueError:
        return None


def n6(s):
    return dec(s, 6)


def n2(s):
    """Pump_Tests decimals are scale 2."""
    return dec(s, 2)


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def yr(s):
    return s[:4] if s and len(s) >= 4 and s[:4].isdigit() else ''


def fmt(v, nd=0):
    if v is None:
        return ''
    if nd == 0:
        return '%d' % round(v)
    return ('%.*f' % (nd, v)).rstrip('0').rstrip('.')


# ------------------------------------------------------------- companies ---
comp = {}
for r in rows('Drilling_Companies'):
    if r.get('Drilling_Company_ID'):
        comp[r['Drilling_Company_ID']] = r.get('Company_Name', '')
print('companies', len(comp))

# ------------------------------------------------------------ pump tests ---
# Keep one test per report: prefer the one with a removal rate, then the latest.
pt = {}
for r in rows('Pump_Tests'):
    k = r.get('Well_Report_ID')
    if not k:
        continue
    rate = n2(r.get('Water_Removal_Rate'))
    swl = n2(r.get('Static_Water_Level'))
    date = r.get('Test_Date', '')
    score = (1 if rate else 0, date)
    cur = pt.get(k)
    if cur is None or score > cur[0]:
        pt[k] = (score, swl, rate, r.get('Water_Removal_Type', ''),
                 r.get('Taken_From_Top_of_Casing', ''), n2(r.get('End_Water_Level')))
print('pump tests', len(pt))

# ----------------------------------------------------------- lithologies ---
# Depth is the bottom of each material, so intervals come from the running top.
lith = collections.defaultdict(list)
nl = 0
for r in rows('Lithologies'):
    k = r.get('Well_Report_ID')
    d = n6(r.get('Depth'))
    if not k or d is None:
        continue
    lith[k].append((d, r.get('Water_Bearing') == 'True', sys.intern(r.get('Material', '')),
                    sys.intern(r.get('Colour', ''))))
    nl += 1
print('lithology rows', nl, 'reports', len(lith))

aq = {}
log = {}
for k, v in lith.items():
    v.sort()
    top = 0.0
    wb = []
    seq = []
    last = None
    for d, w, m, c in v:
        if m and m != last:
            seq.append('%s %d' % (m, round(d)))
            last = m
        elif seq:
            seq[-1] = '%s %d' % (m or last, round(d))
        if w and m:
            wb.append('%d-%d %s' % (round(top), round(d), m))
        top = d
    aq[k] = '; '.join(wb[:6])
    log[k] = '; '.join(seq[:40])
del lith
print('aquifer strings', sum(1 for x in aq.values() if x))

# ----------------------------------------------------------------- wells ---
wells = {}
for r in rows('Wells'):
    wid = r.get('Well_ID')
    lat, lon = fnum(r.get('Latitude')), fnum(r.get('Longitude'))
    if not wid or lat is None or lon is None:
        continue
    if not (48.5 < lat < 60.6 and -121 < lon < -109):
        continue
    lsd, sec, twp, rge, mer = (r.get(x, '') for x in ('LSD', 'Section', 'Township', 'Range', 'Meridian'))
    legal = ''
    if sec and twp and rge and mer:
        legal = '%s-%s-%s-%s-W%sM' % (lsd or '--', sec, twp, rge, mer)
    wells[wid] = (r.get('GIC_Well_ID', wid), lat, lon, fnum(r.get('Elevation')), legal,
                  r.get('GPS_Obtained', ''))
print('wells with coordinates', len(wells))

# --------------------------------------------------------------- reports ---
AGG = {}
nr = 0
for r in rows('Well_Reports'):
    wid = r.get('Well_ID')
    if wid not in wells:
        continue
    rid = r.get('Well_Report_ID')
    a = AGG.get(wid)
    if a is None:
        a = AGG[wid] = {'depth': None, 'use': '', 'work': '', 'drilled': '', 'rate': None,
                        'intake': None, 'casing': None, 'art': None, 'sal': None, 'gas': None,
                        'decom': '', 'driller': '', 'aq': '', 'log': '', 'nl': -1,
                        'swl': None, 'trate': None, 'ttype': '', 'tdatum': '', 'method': ''}
    d = n6(r.get('Total_Depth_Drilled')) or n6(r.get('Finished_Well_Depth'))
    if d and (a['depth'] is None or d > a['depth']):
        a['depth'] = d
    work = r.get('Type_of_Work', '')
    use = r.get('Well_Use', '')
    if use and use != 'Unknown' and (not a['use'] or work == 'New Well'):
        a['use'] = use
    if work and (not a['work'] or work == 'New Well'):
        a['work'] = work
    if 'Decommissioned' in work or r.get('Plug_Date'):
        a['decom'] = r.get('Plug_Date', '') or 'yes'
    y = yr(r.get('Drilling_End_Date'))
    if y and (not a['drilled'] or y < a['drilled']):
        a['drilled'] = y
    for src, key in ((n6(r.get('Recommended_Rate')), 'rate'),
                     (n6(r.get('Recommended_Intake_Depth')), 'intake'),
                     (n6(r.get('Casing_Bottom')), 'casing')):
        if src and (a[key] is None or src > a[key]):
            a[key] = src
    if r.get('Artesian_Flow_Flag') == 'True':
        a['art'] = n6(r.get('Artesian_Flow_Rate')) or a['art'] or 0.0
    if r.get('Encounter_Saline_Water_Flag') == 'True':
        v = n6(r.get('Saline_Water_Depth'))
        if a['sal'] is None or (v and v < a['sal']):
            a['sal'] = v if v is not None else (a['sal'] if a['sal'] is not None else 0.0)
    if r.get('Encounter_Gas_Flag') == 'True':
        v = n6(r.get('Gas_Depth'))
        if a['gas'] is None or (v and v < a['gas']):
            a['gas'] = v if v is not None else (a['gas'] if a['gas'] is not None else 0.0)
    if not a['driller']:
        a['driller'] = comp.get(r.get('Drilling_Company_ID', ''), '')
    if not a['method']:
        a['method'] = r.get('Drilling_Method', '')
    s = aq.get(rid, '')
    g = log.get(rid, '')
    if g and len(g) > a['nl']:
        a['nl'] = len(g)
        a['aq'] = s
        a['log'] = g
    t = pt.get(rid)
    if t and (a['trate'] is None or (t[2] or 0) > (a['trate'] or 0)):
        a['swl'] = t[1]
        a['trate'] = t[2]
        a['ttype'] = t[3]
        a['tdatum'] = 'casing' if t[4] == 'True' else ('ground' if t[4] == 'False' else '')
    nr += 1
print('reports joined', nr, 'wells with a report', len(AGG))

COLS = ['gic', 'lat', 'lon', 'elev', 'legal', 'locsrc', 'use', 'work', 'decom', 'drilled',
        'depth', 'casing', 'rate', 'intake', 'swl', 'swldatum', 'testrate', 'testtype',
        'artesian', 'saline', 'gas', 'method', 'driller', 'aquifer', 'log']
out = gzip.open(FIN, 'wt', encoding='utf-8', compresslevel=9)
out.write('\t'.join(COLS) + '\n')
n = 0
for wid, w in wells.items():
    a = AGG.get(wid)
    if a is None:
        a = {k: (None if k in ('depth', 'rate', 'intake', 'casing', 'art', 'sal', 'gas',
                               'swl', 'trate') else '') for k in
             ('depth', 'use', 'work', 'drilled', 'rate', 'intake', 'casing', 'art', 'sal',
              'gas', 'decom', 'driller', 'aq', 'log', 'swl', 'trate', 'ttype', 'tdatum', 'method')}
    row = [w[0], '%.6f' % w[1], '%.6f' % w[2], fmt(w[3]), w[4], w[5],
           a['use'], a['work'], a['decom'], a['drilled'],
           fmt(a['depth']), fmt(a['casing']), fmt(a['rate'], 1), fmt(a['intake']),
           fmt(a['swl'], 1), a['tdatum'], fmt(a['trate'], 1), a['ttype'],
           fmt(a['art'], 1) if a['art'] is not None else '',
           fmt(a['sal']) if a['sal'] is not None else '',
           fmt(a['gas']) if a['gas'] is not None else '',
           a['method'], a['driller'], a['aq'], a['log']]
    out.write('\t'.join(x.replace('\t', ' ') for x in row) + '\n')
    n += 1
out.close()
print('wrote %d wells -> %.1f MB gz' % (n, os.path.getsize(FIN) / 1e6))
