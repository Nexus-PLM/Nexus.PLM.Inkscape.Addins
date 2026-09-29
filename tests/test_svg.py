"""Where a PLM value lives in an SVG, tested without Inkscape anywhere near it."""

import os
import sys

from lxml import etree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "extension"))

from nexusplm import svg  # noqa: E402


def parse(text):
    return etree.fromstring(text.encode("utf-8"))


PLAIN = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="1" y="1" width="10" height="10"/>
</svg>"""

WITH_LABELLED_TEXT = """<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="100" height="100">
  <text inkscape:label="PartNumber" x="5" y="5"><tspan x="5" y="5">replace me</tspan></text>
  <text inkscape:label="Revision" x="5" y="15"><tspan x="5" y="15">-</tspan></text>
  <text x="5" y="25"><tspan x="5" y="25">not labelled</tspan></text>
</svg>"""


class TestReading:
    def test_a_drawing_never_in_plm_has_no_values(self):
        assert svg.read_values(parse(PLAIN)) == {}

    def test_what_was_written_reads_back(self):
        root = parse(PLAIN)
        svg.write_values(root, {"PartNumber": "DRW-000001-SVG", "Revision": "A"})
        assert svg.read_values(root) == {"PartNumber": "DRW-000001-SVG", "Revision": "A"}

    def test_a_value_survives_a_serialise_and_reparse(self):
        """The record must live through Inkscape writing the file and reading it back."""
        root = parse(PLAIN)
        svg.write_values(root, {"PartNumber": "DRW-000001-SVG"})
        again = parse(etree.tostring(root).decode("utf-8"))
        assert svg.read_values(again) == {"PartNumber": "DRW-000001-SVG"}


class TestWriting:
    def test_writing_twice_updates_rather_than_duplicates(self):
        root = parse(PLAIN)
        svg.write_values(root, {"Revision": "A"})
        svg.write_values(root, {"Revision": "B"})
        assert svg.read_values(root) == {"Revision": "B"}
        # One element, not two: a second write must not leave the first behind.
        assert etree.tostring(root).count(b"<value") <= 1 or \
            len(svg.read_values(root)) == 1

    def test_nothing_to_write_writes_nothing(self):
        root = parse(PLAIN)
        assert svg.write_values(root, {}) == (0, 0)
        assert b"metadata" not in etree.tostring(root)

    def test_a_none_value_is_recorded_as_empty_not_the_word_none(self):
        root = parse(PLAIN)
        svg.write_values(root, {"Description": None})
        assert svg.read_values(root) == {"Description": ""}


class TestDrawing:
    def test_a_labelled_text_element_shows_the_value(self):
        root = parse(WITH_LABELLED_TEXT)
        recorded, drawn = svg.write_values(root, {"PartNumber": "DRW-7", "Revision": "C"})
        assert (recorded, drawn) == (2, 2)
        shown = [t.findall("{http://www.w3.org/2000/svg}tspan")[0].text
                 for t in root.iter("{http://www.w3.org/2000/svg}text")
                 if t.get("{http://www.inkscape.org/namespaces/inkscape}label")]
        assert shown == ["DRW-7", "C"]

    def test_an_unlabelled_text_element_is_left_alone(self):
        root = parse(WITH_LABELLED_TEXT)
        svg.write_values(root, {"PartNumber": "DRW-7"})
        assert b"not labelled" in etree.tostring(root)

    def test_a_value_with_no_labelled_element_is_recorded_but_not_drawn(self):
        """Most drawings show two or three attributes and record all of them."""
        root = parse(WITH_LABELLED_TEXT)
        recorded, drawn = svg.write_values(root, {"Cost": "12.00"})
        assert (recorded, drawn) == (1, 0)
        assert svg.read_values(root) == {"Cost": "12.00"}

    def test_the_old_value_does_not_survive_underneath_the_new_one(self):
        """Setting a <text>'s own text leaves the <tspan> in place and the drawing shows both.

        This is the whole reason _set_text exists rather than a one-line assignment.
        """
        root = parse(WITH_LABELLED_TEXT)
        svg.write_values(root, {"PartNumber": "DRW-7"})
        assert b"replace me" not in etree.tostring(root)

    def test_a_text_element_with_no_tspan_still_takes_the_value(self):
        root = parse("""<svg xmlns="http://www.w3.org/2000/svg"
             xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
          <text inkscape:label="Revision">old</text></svg>""")
        svg.write_values(root, {"Revision": "B"})
        assert b">B<" in etree.tostring(root)
        assert b"old" not in etree.tostring(root)


class TestLabelledKeys:
    def test_it_lists_what_the_drawing_can_show(self):
        assert svg.labelled_keys(parse(WITH_LABELLED_TEXT)) == ["PartNumber", "Revision"]

    def test_a_plain_drawing_shows_nothing(self):
        assert svg.labelled_keys(parse(PLAIN)) == []
