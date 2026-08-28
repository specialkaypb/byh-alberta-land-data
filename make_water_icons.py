#!/usr/bin/env python3
"""Draw the water well icons and merge them into icons_b64.json.

Oil and gas wells are circles in this map, facilities squares, installations
triangles. Water wells get a droplet so the two never read as the same thing at
a glance. Colour carries the yield band; a ring carries a warning.
"""
import base64, io, json, math, os, sys
from PIL import Image, ImageDraw

S = 64
SS = 8  # supersample

RAMP = {
    'wtr_dry':      ('8A3A12', None),
    'wtr_vlow':     ('AD5808', None),
    'wtr_low':      ('BF9263', None),
    'wtr_mod':      ('6E9DBA', None),
    'wtr_good':     ('3A6E8C', None),
    'wtr_high':     ('1F4A63', None),
    'wtr_unk':      ('8A8A76', None),
    # Warnings share a Marshland ring, so the ring means "read this one" and the
    # fill says which warning it is. The plugged well is a fact, not a hazard,
    # so it gets a Twine ring instead.
    'wtr_artesian': ('2E9BC4', '0E1009'),
    'wtr_saline':   ('AD5808', '0E1009'),
    'wtr_gas':      ('D64018', '0E1009'),
    'wtr_plug':     ('431616', 'BF9263'),
}


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def droplet(scale=1.0):
    """Teardrop outline as a polygon, in a unit box with y down.

    Apex above a circle, joined by the two tangent lines, so the point is
    symmetric and the sides meet the bowl without a crease.
    """
    ax, ay = 0.5, 0.045
    cx, cy, r = 0.5, 0.645, 0.305
    d = cy - ay
    phi = math.acos(max(-1.0, min(1.0, r / d)))   # angle at C between CA and CT
    pts = [(ax, ay)]
    n = 96
    for i in range(n + 1):
        th = phi + (2 * math.pi - 2 * phi) * i / n   # clockwise from up, through right
        pts.append((cx + r * math.sin(th), cy - r * math.cos(th)))
    return [((x - 0.5) * scale + 0.5, (y - 0.5) * scale + 0.5) for x, y in pts]


def draw(fill, ring=None):
    im = Image.new('RGBA', (S * SS, S * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if ring:
        dr.polygon([(x * S * SS, y * S * SS) for x, y in droplet(1.0)], fill=rgb(ring) + (255,))
        dr.polygon([(x * S * SS, y * S * SS) for x, y in droplet(0.72)], fill=rgb(fill) + (255,))
    else:
        dr.polygon([(x * S * SS, y * S * SS) for x, y in droplet(1.0)], fill=rgb(fill) + (255,))
    return im.resize((S, S), Image.LANCZOS)


def main():
    path = sys.argv[1]
    icons = json.load(open(path))
    sheet = Image.new('RGBA', (S * len(RAMP), S), (240, 230, 209, 255))
    for i, (k, (fill, ring)) in enumerate(RAMP.items()):
        im = draw(fill, ring)
        b = io.BytesIO()
        im.save(b, 'PNG', optimize=True)
        icons[k] = base64.b64encode(b.getvalue()).decode('ascii')
        sheet.paste(im, (S * i, 0), im)
    json.dump(icons, open(path, 'w'))
    sheet.resize((S * len(RAMP) * 2, S * 2), Image.NEAREST).save('/tmp/watericons.png')
    print('%d icons in %s, %d added' % (len(icons), path, len(RAMP)))


if __name__ == '__main__':
    main()
