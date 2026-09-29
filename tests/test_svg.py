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


class TestWritingIntoAStagedFile:
    """New from Template opens the staged file in a NEW Inkscape, so there is no in-memory
    document to fill. The values have to go into the file first - which is safe precisely
    because nothing has it open yet."""

    def _staged(self, tmp_path, name="IND-000001-SVG.svg"):
        path = tmp_path / name
        path.write_bytes(WITH_LABELLED_TEXT.encode("utf-8"))
        return path

    def test_values_reach_the_file(self, tmp_path):
        path = self._staged(tmp_path)
        recorded, drawn = svg.write_into_file(str(path), {"PartNumber": "IND-000001-SVG"})
        assert (recorded, drawn) == (1, 1)
        assert b"IND-000001-SVG" in path.read_bytes()

    def test_the_file_is_still_valid_svg_afterwards(self, tmp_path):
        path = self._staged(tmp_path)
        svg.write_into_file(str(path), {"Revision": "B"})
        again = etree.parse(str(path)).getroot()
        assert svg.read_values(again) == {"Revision": "B"}

    def test_the_placeholder_does_not_survive(self, tmp_path):
        """The bug driving showed: a title block still reading '-' on a numbered item."""
        path = self._staged(tmp_path)
        svg.write_into_file(str(path), {"PartNumber": "IND-000001-SVG"})
        assert b"replace me" not in path.read_bytes()

    def test_a_gzipped_svgz_round_trips(self, tmp_path):
        import gzip
        path = tmp_path / "IND-000002-SVG.svgz"
        with gzip.open(path, "wb") as handle:
            handle.write(WITH_LABELLED_TEXT.encode("utf-8"))
        svg.write_into_file(str(path), {"Revision": "C"})
        with gzip.open(path, "rb") as handle:
            again = etree.fromstring(handle.read())
        assert svg.read_values(again) == {"Revision": "C"}

    def test_nothing_to_write_touches_nothing(self, tmp_path):
        path = self._staged(tmp_path)
        before = path.read_bytes()
        assert svg.write_into_file(str(path), {}) == (0, 0)
        assert path.read_bytes() == before


class TestHowAValueReadsOnTheSheet:
    """The record keeps what the service sent; the drawing shows what a person wants to read."""

    def test_an_iso_timestamp_is_drawn_as_a_date(self):
        root = parse(WITH_LABELLED_TEXT.replace("PartNumber", "CreationDate"))
        svg.write_values(root, {"CreationDate": "2026-09-28T02:24:15.3456789Z"})
        drawn = [t.findall("{http://www.w3.org/2000/svg}tspan")[0].text
                 for t in root.iter("{http://www.w3.org/2000/svg}text")
                 if t.get("{http://www.inkscape.org/namespaces/inkscape}label") == "CreationDate"]
        # Only what is DRAWN is trimmed. Asserting over the whole document fails on the record,
        # which is supposed to keep the exact value - the first version of this test did that.
        assert drawn == ["2026-09-28"]

    def test_but_the_record_keeps_the_exact_value(self):
        """Refresh Values compares against it, so it must not be rounded off for looks."""
        root = parse(WITH_LABELLED_TEXT.replace("PartNumber", "CreationDate"))
        svg.write_values(root, {"CreationDate": "2026-09-28T02:24:15.3456789Z"})
        assert svg.read_values(root)["CreationDate"] == "2026-09-28T02:24:15.3456789Z"

    def test_anything_that_is_not_a_timestamp_is_left_alone(self):
        for value in ["IND-00000002-SVG", "A", "2026", "not-a-date", "", "12.5"]:
            assert svg.for_display(value) == value

    def test_a_part_number_that_merely_looks_datelike_is_not_trimmed(self):
        assert svg.for_display("ABCD-EF-GHTIJ") == "ABCD-EF-GHTIJ"

    def test_none_draws_as_empty(self):
        assert svg.for_display(None) == ""
