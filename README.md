# Alberta land data pack

Tiled Alberta open data for the `byh-alberta-property-map` skill. The skill reads
tiles over HTTPS straight out of this repo:

    https://raw.githubusercontent.com/specialkaypb/byh-alberta-land-data/main

No token, no login. Set that as `BYH_PACK_BASE` and a build fetches only the one
to four tiles its query circle touches, a few megabytes rather than the whole 86 MB.

## Contents

| File | What it is |
|---|---|
| `manifest.json` | grid definition, column names, per-tile record counts |
| `ats_index.json.gz` | legal land description index, 94,748 sections and 5,720 townships |
| `qs_lsrs.tsv.gz` | dominant soil capability class for 387,590 quarter sections |
| `tiles/` | 60 tiles covering Alberta, largest 6.7 MB |

Records in the pack: 539,475 oil and gas wells, 351,486 pipeline segments,
124,948 facilities, 4,466 pipeline installations, 145 field-corrected well
positions, 29,146 soil landscape polygons, 453,398 water wells.

Line and polygon features are written into every tile their bounding box touches,
so a pipeline crossing a tile edge appears in both. The builder deduplicates on
load, which is why the per-tile counts in `manifest.json` add up to more than the
totals above.

## Rebuild tooling

Everything needed to regenerate the pack from source is here.

| Script | Job |
|---|---|
| `extract_shapefiles.py` | streams the AER shapefile and dBase records straight out of their ZIPs into compact TSVs, no GIS dependencies |
| `extract_soil.py`, `extract_qs.py` | the same for AGRASID soil landscapes and the quarter-section capability table |
| `awwid_open.py`, `awwid_stream.py`, `awwid_extract.py`, `awwid_join.py` | read the 2.1 GB AWWID Access database without loading it into RAM, then join it down to one row per water well |
| `make_pack.py` | tiles everything into `tiles/` and writes `manifest.json` |
| `make_water_icons.py` | draws the water well map icons |

Two traps if you go back to the AWWID source yourself. Every number in it is
imperial: feet, imperial gallons per minute, inches. And its decimal columns
carry a per-column scale, 8 for well coordinates and elevation, 6 for the
drilling report and lithology tables, 2 for pump tests. Use the wrong scale and
static water levels come out a hundred times too small while still looking
plausible.

Full procedure, including the source download URLs, is in `references/pack.md`
inside the skill.

## Sources and attribution

**Oil and gas.** Alberta Energy Regulator public spatial data (ST37, ST102,
Enhanced Pipeline, Abandoned Well Map, Revised Abandoned Well Locations).

**Soil.** AGRASID 4.1, Alberta Agriculture and Irrigation with Agriculture and
Agri-Food Canada. The AGRASID metadata states the data remains the property of
AAFC and AAF and that any derivative product must reference the original source.
That credit is carried in every map and document the skill produces, and must
stay there.

**Water wells.** Government of Alberta, Alberta Water Well Information Database.
Retrieved 28 August 2026, from http://groundwater.alberta.ca/WaterWells/d/

That wording is the citation the province asks for, and it belongs in anything
built from this layer.

Licensed under the [Open Government Licence - Alberta](https://open.alberta.ca/licence),
version 2.2, which grants commercial use and redistribution with attribution.
Personal information is excluded from that grant, so the `Well_Owners` table was
never read and no owner name or address appears anywhere in this pack.
