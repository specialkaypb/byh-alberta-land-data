"""Stream rows out of an AWWID table without holding the whole table in RAM."""
import logging, struct, time
from collections import defaultdict
logging.disable(logging.ERROR)
import awwid_open
from access_parser import access_parser as ap
from access_parser import parsing_primitives as pp

# Upstream builds a construct Struct per call; this is the same fields, hand rolled.
class _Hdr(object):
    __slots__ = ('data_free_space', 'owner', 'record_count', 'record_offsets')

def _fast_header(buffer, version=3):
    h = _Hdr()
    if version > 3:
        h.data_free_space, h.owner, _u, h.record_count = struct.unpack_from('<HIIH', buffer, 2)
        base = 14
    else:
        h.data_free_space, h.owner, h.record_count = struct.unpack_from('<HIH', buffer, 2)
        base = 10
    h.record_offsets = struct.unpack_from('<%dH' % h.record_count, buffer, base)
    return h

ap.parse_data_page_header = _fast_header
pp.parse_data_page_header = _fast_header


def stream(db, name, cols=None, batch_pages=400, deadline=None):
    """Yield (colname -> list) chunks. cols filters the output keys."""
    t = db.get_table(name)
    if t is None:
        return
    pages = t.table.linked_pages
    n = len(pages)
    d = pages._d
    ps = pages._ps
    offsets = list(list.__iter__(pages))
    for start in range(0, n, batch_pages):
        sub = awwid_open.LazyPageList(d, ps)
        for o in offsets[start:start + batch_pages]:
            list.append(sub, o)
        t.table.linked_pages = sub
        t.parsed_table = defaultdict(list)
        try:
            out = t.parse()
        except Exception:
            continue
        if cols:
            out = {c: out.get(c, []) for c in cols}
        yield start, n, out
        if deadline and time.time() > deadline:
            return
