"""The Inkscape-shaped helpers, tested against real files and a fake extension."""

import os
import sys

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "extension"))

import pytest  # noqa: E402

from nexusplm import host  # noqa: E402

DRAWING = """<svg xmlns="http://www.w3.org/2000/svg"><rect x="1" y="1" width="9" height="9"/></svg>"""


@pytest.fixture(autouse=True)
def never_the_real_log(tmp_path, monkeypatch):
    """No test may write to the user's actual add-in log.

    One of these did, and the line turned up in a live driving session where it read as something
    the add-in had just done. A test that leaves a trace in a real diagnostic is a test that will
    mislead somebody at the worst moment.
    """
    monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "logs" / "addin.log"))


class FakeSvgProxy:
    def __init__(self, root):
        self._tree = root.getroottree()

    def getroottree(self):
        return self._tree


class FakeExtension:
    def __init__(self, text=DRAWING, path=None):
        self.svg = FakeSvgProxy(etree.fromstring(text.encode("utf-8")))
        self._path = path

    def document_path(self):
        return self._path


class TestDocumentPath:
    def test_a_saved_drawing_answers_its_path(self):
        assert host.document_path(FakeExtension(path=r"C:\drawings\DRW-1.svg")) \
            == r"C:\drawings\DRW-1.svg"

    def test_never_saved_is_none_not_an_empty_string(self):
        """inkex says "" for never-saved and None for "this Inkscape cannot tell".

        Both mean the same thing to a command, so both become None and there is one case to
        handle instead of three.
        """
        assert host.document_path(FakeExtension(path="")) is None
        assert host.document_path(FakeExtension(path=None)) is None


class TestUploadCopy:
    """What PLM is given: the on-screen drawing, written to the document's OWN path.

    Not a temp copy. SaveRequest has one FilePath that the service reads AND records as the
    item's plm_file_path, so a temp path became the next revision's home - Revise staged rev B
    under %TEMP% and opened a second window. Marc: "it must get written to the staging directory".
    """

    def test_it_writes_the_open_drawing_over_the_file_and_answers_that_path(self, tmp_path):
        on_disk = tmp_path / "DRW-1.svg"
        on_disk.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'><!-- stale --></svg>")
        edited = FakeExtension(
            """<svg xmlns="http://www.w3.org/2000/svg"><rect id="fresh" x="9" y="9"/></svg>""")

        sent = host.upload_copy(edited, str(on_disk))

        assert sent == str(on_disk)
        body = on_disk.read_bytes()
        assert b"fresh" in body and b"stale" not in body

    def test_the_file_is_well_formed_xml_with_a_declaration(self, tmp_path):
        path = tmp_path / "DRW-1.svg"
        host.upload_copy(FakeExtension(), str(path))
        body = path.read_bytes()
        assert body.startswith(b"<?xml")
        etree.fromstring(body)          # raises if the file is not parseable

    def test_a_drawing_with_no_file_is_refused_not_guessed(self):
        """A made-up name under %TEMP% is exactly the bug this replaced."""
        with pytest.raises(ValueError):
            host.upload_copy(FakeExtension(), None)


class TestSameFile:
    def test_case_and_slashes_do_not_matter_on_windows(self):
        assert host.same_file(r"C:\Nexus\Staging\DRW-1.svg", "c:/nexus/staging/drw-1.svg")

    def test_different_files_differ(self):
        assert not host.same_file(r"C:\Nexus\Staging\DRW-1.svg", r"C:\Nexus\Staging\DRW-2.svg")

    def test_nothing_is_never_the_same_file(self):
        assert not host.same_file(None, r"C:\x.svg")
        assert not host.same_file(r"C:\x.svg", "")


class TestReplaceDocument:
    """How Revise ups the revision in place: the staged file becomes the extension's output."""

    def test_the_staged_file_becomes_the_document_as_a_parsed_tree(self, tmp_path):
        """A tree, not bytes: inkex's has_changed calls etree.tostring on it before save does."""
        staged = tmp_path / "DRW-1.svg"
        staged.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><rect id="revB"/></svg>')
        extension = FakeExtension()
        host.replace_document(extension, str(staged))
        assert hasattr(extension.document, "getroot")
        assert b'id="revB"' in etree.tostring(extension.document)

    def test_the_root_is_refreshed_too(self, tmp_path):
        staged = tmp_path / "DRW-1.svg"
        staged.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><rect id="revB"/></svg>')
        extension = FakeExtension()
        host.replace_document(extension, str(staged))
        assert extension.svg.find("{http://www.w3.org/2000/svg}rect").get("id") == "revB"


class TestLogging:
    def test_a_line_is_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "logs" / "addin.log"))
        host.log("check-out: started")
        assert "check-out: started" in open(host.LOG_PATH, encoding="utf-8").read()

    def test_a_log_that_cannot_be_written_does_not_fail_the_command(self, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", "\x00:/nowhere/addin.log")
        host.log("this must not raise")
