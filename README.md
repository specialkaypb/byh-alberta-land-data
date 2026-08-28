# Alberta land data pack

Tiled Alberta open data for the `byh-alberta-property-map` skill. Upload this whole
folder to the root of a public GitHub repo. The skill then reads tiles over HTTPS from

    https://raw.githubusercontent.com/<user>/<repo>/main

## Contents
- `manifest.json` grid definition, column names, per-tile record counts
- `ats_index.json.gz` legal land description index, 94,748 sections
- `qs_lsrs.tsv.gz` dominant soil capability class for 387,590 quarter sections
- `tiles/` 60 tiles covering Alberta, largest 6.7 MB
- `extract_shapefiles.py`, `extract_soil.py`, `extract_qs.py`, `awwid_*.py`,
  `make_pack.py` rebuild tooling

## Sources and attribution

**Oil and gas.** Alberta Energy Regulator public spatial data (ST37, ST102, Enhanced
Pipeline, Abandoned Well Map, Revised Abandoned Well Locations).

**Soil.** AGRASID 4.1, Alberta Agriculture and Irrigation with Agriculture and Agri-Food
Canada. The AGRASID metadata states the data remains the property of AAFC and AAF and
that any derivative product must reference the original source. That credit is carried
in every map and document the skill produces, and must stay there.

**Water wells.** Government of Alberta, Alberta Water Well Information Database.
Retrieved 28 August 2026, from http://groundwater.alberta.ca/WaterWells/d/ — that
wording is the citation the province asks for, and it belongs in anything built from
this layer.

Licensed under the [Open Government Licence - Alberta](https://open.alberta.ca/licence),
version 2.2, which grants commercial use and redistribution with attribution. Personal
information is excluded from that grant, so the `Well_Owners` table was never read and
no owner name or address appears anywhere in this pack.
