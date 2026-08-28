"""Memory-safe AWWID .mdb reader."""
import mmap, os, sys
PYLIB = os.environ.get('BYH_PYLIB')
if PYLIB and PYLIB not in sys.path:
    sys.path.insert(0, PYLIB)
from access_parser import access_parser as ap
from access_parser.utils import DATA_PAGE_MAGIC, TABLE_PAGE_MAGIC
_HANDLES = []
def _read_db_file(path):
    f = open(path, 'rb')
    m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    _HANDLES.append((f, m))
    return m
class LazyPages(object):
    def __init__(self, data, page_size, keys=None):
        self.d = data; self.ps = page_size; self.n = len(data); self.k = keys
    def _ok(self, i):
        if self.k is not None: return i in self.k
        return 0 <= i < self.n and i % self.ps == 0
    def __getitem__(self, i):
        if not self._ok(i): raise KeyError(i)
        return self.d[i:i + self.ps]
    def __contains__(self, i): return self._ok(i)
    def get(self, i, default=None): return self[i] if self._ok(i) else default
    def keys(self):
        if self.k is not None: return sorted(self.k)
        return range(0, self.n - self.n % self.ps, self.ps)
    def __iter__(self): return iter(self.keys())
    def __len__(self): return len(self.k) if self.k is not None else self.n // self.ps
    def items(self):
        for i in self.keys(): yield i, self.d[i:i + self.ps]
def _categorize_pages(db_data, page_size):
    data_keys = set(); table_keys = set(); n = len(db_data)
    for i in range(0, n - n % page_size, page_size):
        head = db_data[i:i + 2]
        if head == DATA_PAGE_MAGIC: data_keys.add(i)
        elif head == TABLE_PAGE_MAGIC: table_keys.add(i)
    return (LazyPages(db_data, page_size, table_keys),
            LazyPages(db_data, page_size, data_keys),
            LazyPages(db_data, page_size))
ap.read_db_file = _read_db_file
ap.categorize_pages = _categorize_pages
def open_db(path): return ap.AccessParser(path)


import struct as _struct


class LazyPageList(list):
    """Stores page offsets, yields page bytes sliced from the mmap."""

    def __init__(self, data, ps):
        list.__init__(self)
        self._d = data
        self._ps = ps

    def __iter__(self):
        d, ps = self._d, self._ps
        for off in list.__iter__(self):
            yield d[off:off + ps]

    def __getitem__(self, i):
        off = list.__getitem__(self, i)
        return self._d[off:off + self._ps]


def _link_tables_to_data(self):
    """Same job as upstream, without a construct parse per page.

    owner is a little-endian uint32 at byte 4 of every data page header.
    """
    tables = {}
    d = self.db_data
    ps = self.page_size
    tdefs = self._table_defs
    for offset in self._data_pages.keys():
        page_offset = _struct.unpack_from('<I', d, offset + 4)[0] * ps
        if page_offset in tdefs:
            t = tables.get(page_offset)
            if t is None:
                t = ap.TableObj(page_offset, tdefs.get(page_offset))
                t.linked_pages = LazyPageList(d, ps)
                tables[page_offset] = t
            list.append(t.linked_pages, offset)
    return tables


ap.AccessParser._link_tables_to_data = _link_tables_to_data
