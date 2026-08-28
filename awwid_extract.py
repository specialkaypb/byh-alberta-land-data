"""Extract the AWWID tables the property map needs into compact TSVs.

Runs in resumable slices because each shell call on this device is capped at
45 seconds. State lives beside the output in /tmp/byhw/out.

Deliberately omits Well_Owners and every owner name field. Owner names are
personal information about identifiable landowners, which the Open Government
Licence - Alberta explicitly does not grant the right to use.
"""
import os, sys, time, struct, json, multiprocessing as mp
from collections import defaultdict

OUT = '/tmp/byhw/out'
MDB = '/tmp/byhw/w.mdb'
BATCH = 200

import awwid_open, awwid_stream
from access_parser.utils import numeric_to_string

# table -> (columns to keep, decimal columns needing scale decode)
SPEC = {
    'Wells': (['Well_ID', 'GIC_Well_ID', 'Latitude', 'Longitude', 'Elevation',
               'LSD', 'Section', 'Township', 'Range', 'Meridian',
               'GPS_Obtained', 'Validated_Flag'], None),
    'Well_Reports': (['Well_Report_ID', 'Well_ID', 'Drilling_Company_ID', 'Well_Use',
                      'Other_Well_Use', 'Type_of_Work', 'Total_Depth_Drilled',
                      'Finished_Well_Depth', 'Drilling_End_Date', 'Plug_Date',
                      'Casing_Bottom', 'Artesian_Flow_Flag', 'Artesian_Flow_Rate',
                      'Encounter_Saline_Water_Flag', 'Saline_Water_Depth',
                      'Encounter_Gas_Flag', 'Gas_Depth', 'Recommended_Rate',
                      'Recommended_Intake_Depth', 'Drilling_Method'], None),
    'Pump_Tests': (['Pump_Test_ID', 'Well_Report_ID', 'Test_Date', 'Static_Water_Level',
                    'End_Water_Level', 'Water_Removal_Type', 'Water_Removal_Rate',
                    'Removal_Depth_From', 'Taken_From_Top_of_Casing'], None),
    'Lithologies': (['Well_Report_ID', 'Depth', 'Water_Bearing', 'Material',
                     'Colour', 'Description'], None),
    'Drilling_Companies': (['Drilling_Company_ID', 'Company_Name', 'City', 'Province'], None),
    'Screens': (['Well_Report_ID', 'From', 'To', 'Slot_Size'], None),
    'Chemical_Analysis': (['Chemical_Analysis_ID', 'Well_ID', 'Well_Report_ID',
                           'Sample_Date', 'Water_Level', 'Aquifer'], None),
}


def cell(v):
    if v is None:
        return ''
    if isinstance(v, bytes):
        if len(v) == 17:
            try:
                s = numeric_to_string(v, 8)
                return '' if s in ('0.00000000', '-0.00000000') else s
            except Exception:
                return ''
        return ''
    s = str(v).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ').strip()
    if s in ('None', '(Empty Date)', '(Invalid Date)'):
        return ''
    return s


def worker(name, cols, lo, hi, part):
    state = os.path.join(OUT, '%s.%d.state' % (name, part))
    path = os.path.join(OUT, '%s.%d.tsv' % (name, part))
    start = lo
    if os.path.exists(state):
        start = int(open(state).read().strip() or lo)
    if start >= hi:
        return
    deadline = float(os.environ.get('BYH_DEADLINE', time.time() + 30))
    db = DB
    t = db.get_table(name)
    pages = t.table.linked_pages
    offsets = list(list.__iter__(pages))
    d, ps = pages._d, pages._ps
    mode = 'a' if os.path.exists(path) else 'w'
    f = open(path, mode)
    if mode == 'w' and part == 0:
        f.write('\t'.join(cols) + '\n')
    pos = start
    while pos < hi and time.time() < deadline:
        sub = awwid_open.LazyPageList(d, ps)
        for o in offsets[pos:min(pos + BATCH, hi)]:
            list.append(sub, o)
        t.table.linked_pages = sub
        t.parsed_table = defaultdict(list)
        try:
            out = t.parse()
        except Exception:
            out = {}
        series = [out.get(c, []) for c in cols]
        n = max((len(s) for s in series), default=0)
        buf = []
        for i in range(n):
            buf.append('\t'.join(cell(s[i]) if i < len(s) else '' for s in series))
        if buf:
            f.write('\n'.join(buf) + '\n')
        pos = min(pos + BATCH, hi)
        open(state, 'w').write(str(pos))
    f.close()


DB = None


def main():
    global DB
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    only = sys.argv[2:] or list(SPEC)
    os.makedirs(OUT, exist_ok=True)
    DB = awwid_open.open_db(MDB)
    deadline = time.time() + budget
    os.environ['BYH_DEADLINE'] = str(deadline)
    for name in only:
        if time.time() >= deadline - 2:
            break
        cols = SPEC[name][0]
        t = DB.get_table(name)
        if t is None:
            print(name, 'MISSING')
            continue
        n = len(t.table.linked_pages)
        mid = (n // 2 // BATCH) * BATCH
        done = 0
        for p, (lo, hi) in enumerate(((0, mid), (mid, n))):
            s = os.path.join(OUT, '%s.%d.state' % (name, p))
            done += (int(open(s).read().strip()) if os.path.exists(s) else lo) - lo
        total = n
        if done >= total:
            print('%-20s complete (%d pages)' % (name, n))
            continue
        procs = []
        for p, (lo, hi) in enumerate(((0, mid), (mid, n))):
            pr = mp.Process(target=worker, args=(name, cols, lo, hi, p))
            pr.start()
            procs.append(pr)
        for pr in procs:
            pr.join()
        done2 = 0
        for p, (lo, hi) in enumerate(((0, mid), (mid, n))):
            s = os.path.join(OUT, '%s.%d.state' % (name, p))
            done2 += (int(open(s).read().strip()) if os.path.exists(s) else lo) - lo
        print('%-20s %d/%d pages (%.0f%%)' % (name, done2, total, 100.0 * done2 / total))


if __name__ == '__main__':
    mp.set_start_method('fork')
    main()
