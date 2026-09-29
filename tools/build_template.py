#!/usr/bin/env python3
"""Build the Inkscape Drawing template - an A4 sheet with a PLM title block.

The template is what makes New from Template worth having: a drawing that already knows where its
part number goes. Every value the type maps is recorded in ``<metadata>``; the six worth seeing
are drawn in the title block, in text elements labelled with the attribute's key. The add-in fills
them by matching ``inkscape:label`` - see ``nexusplm/svg.py``.

Generated rather than hand-drawn so the labels cannot drift from the connector mapping, and so
anyone can rebuild it:

    python tools/build_template.py                  # writes dist/Inkscape Drawing.svg
    python tools/build_template.py --out somewhere.svg
"""

import argparse
import os

#: The fields the title block shows. Every other mapped attribute is still recorded in metadata;
#: these are the ones a person reads off the sheet. The keys must match the connector mapping's
#: templateField values exactly, because that is what the add-in matches on.
SHOWN = [
    ("PartNumber",   "PART NUMBER"),
    ("Revision",     "REV"),
    ("Description",  "DESCRIPTION"),
    ("Author",       "AUTHOR"),
    ("Department",   "DEPARTMENT"),
    ("CreationDate", "DATE"),
]

#: Recorded in metadata but not drawn - there is nowhere sensible on a sheet for them and the
#: record is what the service reads back.
RECORDED_ONLY = ["CreatedBy", "ModifiedBy", "ModificationDate", "Approved", "Priority"]

WIDTH, HEIGHT = 297.0, 210.0          # A4 landscape, millimetres
MARGIN = 8.0
BLOCK_W, BLOCK_H = 150.0, 46.0
ROW_H = BLOCK_H / 3.0

SVG = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
     xmlns:nexus="https://nexusplm.com/ns/plm"
     width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}" version="1.1">
  <title>Inkscape Drawing</title>
  <metadata>
    <nexus:attributes>
{recorded}
    </nexus:attributes>
  </metadata>
  <sodipodi:namedview inkscape:document-units="mm" showgrid="false"/>

  <g inkscape:groupmode="layer" inkscape:label="Sheet" id="layer-sheet">
    <rect x="{m}" y="{m}" width="{iw}" height="{ih}"
          fill="none" stroke="#000000" stroke-width="0.5"/>
{block}
  </g>

  <g inkscape:groupmode="layer" inkscape:label="Drawing" id="layer-drawing"/>
</svg>
'''


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build():
    left = WIDTH - MARGIN - BLOCK_W
    top = HEIGHT - MARGIN - BLOCK_H

    parts = [
        '    <rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#ffffff" '
        'stroke="#000000" stroke-width="0.5"/>' % (left, top, BLOCK_W, BLOCK_H)
    ]

    # Two columns of three rows. A labelled <text> per field, with the <tspan> the add-in
    # rewrites - svg.py keeps the first tspan's styling and replaces its text.
    for index, (key, caption) in enumerate(SHOWN):
        column, row = divmod(index, 3)
        x = left + 3.0 + column * (BLOCK_W / 2.0)
        y = top + ROW_H * (row + 1) - 4.5

        parts.append(
            '    <text x="%.3f" y="%.3f" font-family="sans-serif" font-size="2.6" '
            'fill="#666666" xml:space="preserve">'
            '<tspan x="%.3f" y="%.3f">%s</tspan></text>'
            % (x, y, x, y, escape(caption)))
        parts.append(
            '    <text inkscape:label="%s" x="%.3f" y="%.3f" font-family="sans-serif" '
            'font-size="4.2" fill="#000000" xml:space="preserve">'
            '<tspan x="%.3f" y="%.3f">-</tspan></text>'
            % (escape(key), x, y + 5.2, x, y + 5.2))

    # Horizontal rules between the rows, and the column divider.
    for row in (1, 2):
        parts.append('    <line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#000000" '
                     'stroke-width="0.25"/>'
                     % (left, top + ROW_H * row, left + BLOCK_W, top + ROW_H * row))
    parts.append('    <line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#000000" '
                 'stroke-width="0.25"/>'
                 % (left + BLOCK_W / 2.0, top, left + BLOCK_W / 2.0, top + BLOCK_H))

    recorded = "\n".join(
        '      <nexus:value key="%s"></nexus:value>' % escape(key)
        for key, _caption in SHOWN) + "\n" + "\n".join(
        '      <nexus:value key="%s"></nexus:value>' % escape(key)
        for key in RECORDED_ONLY)

    return SVG.format(w=WIDTH, h=HEIGHT, m=MARGIN,
                      iw=WIDTH - 2 * MARGIN, ih=HEIGHT - 2 * MARGIN,
                      block="\n".join(parts), recorded=recorded)


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join(here, "dist", "Inkscape Drawing.svg"))
    arguments = parser.parse_args()

    os.makedirs(os.path.dirname(arguments.out), exist_ok=True)
    with open(arguments.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(build())

    print("wrote %s" % arguments.out)
    print("shown in the title block: %s" % ", ".join(k for k, _ in SHOWN))
    print("recorded only:            %s" % ", ".join(RECORDED_ONLY))


if __name__ == "__main__":
    main()
