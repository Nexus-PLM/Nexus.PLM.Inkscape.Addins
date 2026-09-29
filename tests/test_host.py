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
    """What PLM is given: the drawing on screen, written under the document's own name."""

    def test_it_writes_the_open_drawing_not_the_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        on_disk = tmp_path / "DRW-1.svg"
        on_disk.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'><!-- stale --></svg>")

        edited = FakeExtension(
            """<svg xmlns="http://www.w3.org/2000/svg"><rect id="fresh" x="9" y="9"/></svg>""")
        copy = host.upload_copy(edited, str(on_disk))

        assert copy != str(on_disk)
        body = open(copy, "rb").read()
        assert b"fresh" in body
        assert b"stale" not in body

    def test_it_keeps_the_documents_file_name(self, tmp_path, monkeypatch):
        """The vault names a dataset from it and /plm/state reads the part number back out."""
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        copy = host.upload_copy(FakeExtension(), r"C:\drawings\DRW-000009-SVG.svg")
        assert os.path.basename(copy) == "DRW-000009-SVG.svg"

    def test_a_never_saved_drawing_still_produces_a_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        copy = host.upload_copy(FakeExtension(), None)
        assert os.path.basename(copy) == "Untitled.svg"
        assert os.path.isfile(copy)

    def test_the_copy_is_well_formed_xml_with_a_declaration(self, tmp_path, monkeypatch):
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        copy = host.upload_copy(FakeExtension(), r"C:\drawings\DRW-1.svg")
        body = open(copy, "rb").read()
        assert body.startswith(b"<?xml")
        etree.fromstring(body)          # raises if the copy is not parseable


class TestLogging:
    def test_a_line_is_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "logs" / "addin.log"))
        host.log("check-out: started")
        assert "check-out: started" in open(host.LOG_PATH, encoding="utf-8").read()

    def test_a_log_that_cannot_be_written_does_not_fail_the_command(self, monkeypatch):
        monkeypatch.setattr(host, "LOG_PATH", "\x00:/nowhere/addin.log")
        host.log("this must not raise")
