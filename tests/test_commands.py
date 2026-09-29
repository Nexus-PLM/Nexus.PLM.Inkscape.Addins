"""The command bodies, driven with a fake service and no Inkscape at all."""

import os
import sys

import pytest
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "extension"))

from nexusplm import commands, host, svg  # noqa: E402
from nexusplm.client import ServiceUnavailable  # noqa: E402

import build  # noqa: E402  - the .inx generator, imported for its MENU table


SVG_TEXT = """<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <text inkscape:label="PartNumber"><tspan>-</tspan></text>
</svg>"""


class FakeSvgProxy:
    """Stands in for ``extension.svg``, which only has to answer ``getroottree``."""

    def __init__(self, root):
        self._tree = root.getroottree()

    def getroottree(self):
        return self._tree


class FakeExtension:
    def __init__(self, text=SVG_TEXT, path="C:/drawings/DRW-000001-SVG.svg"):
        self.svg = FakeSvgProxy(etree.fromstring(text.encode("utf-8")))
        self._path = path

    def document_path(self):
        return self._path


class FakeClient:
    """Records what was asked of it and answers whatever the test set up."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []
        self.said = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append(name)
            return self.answers.get(name, {"success": True})
        return call

    def notify(self, message, severity="info"):
        self.said.append((severity, message))
        self.calls.append("notify")
        return {"success": True}


@pytest.fixture(autouse=True)
def no_real_side_effects(monkeypatch, tmp_path):
    """Never write the real log, never launch Inkscape, never open a browser."""
    monkeypatch.setattr(host, "LOG_PATH", str(tmp_path / "addin.log"))
    monkeypatch.setattr(host, "open_document", lambda path: None)
    monkeypatch.setattr(host, "open_url", lambda url: None)


def context(client=None, extension=None, path="C:/drawings/DRW-000001-SVG.svg"):
    extension = extension or FakeExtension(path=path)
    return commands.Context(client or FakeClient(), extension, path)


class TestTheMenuAndTheCommandsAgree:
    """A menu entry with no command is a dead entry; a command with no entry is unreachable.

    Generated files and a dispatch table are two lists of the same thing, which is exactly the
    shape that drifts. This is the Inkscape equivalent of the Office add-in's rule that a fix
    landing in Word cannot stop there.
    """

    def test_every_menu_entry_has_a_command(self):
        missing = [c for c, _ in build.MENU if c not in commands.COMMANDS]
        assert missing == []

    def test_every_command_is_on_the_menu(self):
        on_menu = {c for c, _ in build.MENU}
        assert sorted(set(commands.COMMANDS) - on_menu) == []

    def test_every_menu_entry_has_a_distinct_id(self):
        ids = [build.ID_PREFIX + "." + c for c, _ in build.MENU]
        assert len(ids) == len(set(ids))

    def test_no_entry_claims_to_work_without_a_document(self, tmp_path):
        """`needs-document="false"` kills the command before it runs.

        Measured on Inkscape 1.4.2: an EffectExtension launched with no document dies inside
        inkex's own loader - `'NoneType' object has no attribute 'selection'` - and Inkscape puts
        that traceback in front of the user. It is a tempting attribute, because Sign In really
        does not need a drawing, so this test is here to stop it coming back.
        """
        build.write_inx(str(tmp_path))
        for command, _label in build.MENU:
            body = (tmp_path / build.inx_name(command)).read_text(encoding="utf-8")
            assert "needs-document" not in body, command


class TestAnUnregisteredDrawing:
    def test_it_is_told_so_rather_than_failing(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: None)
        client = FakeClient()
        commands.check_out(context(client))
        assert any("not registered in PLM" in m for _s, m in client.said)

    def test_and_no_call_is_made_on_its_behalf(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: None)
        client = FakeClient()
        commands.check_out(context(client))
        assert "check_out" not in client.calls


class TestAnUnsavedDrawing:
    def test_save_as_new_says_to_save_first(self):
        client = FakeClient()
        commands.save_as_new(context(client, path=None))
        assert any("never been saved" in m for _s, m in client.said)
        assert "save_as_new" not in client.calls


class TestWhatGetsUploaded:
    """PLM is given the drawing on screen, not the file on disk.

    The first version compared the two and refused when they differed. Inkscape's in-memory
    document is never byte-identical to its file - it carries sodipodi:namedview and its own
    version stamp - so that refused a drawing nobody had touched. These tests hold the fix.
    """

    def test_save_to_plm_sends_a_copy_of_the_open_drawing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        client = FakeClient()
        ctx = context(client)
        sent = {}
        monkeypatch.setattr(client, "save",
                            lambda item_id, path: sent.update(item=item_id, path=path)
                            or {"success": True})
        commands.save_to_plm(ctx)
        assert sent["path"] != ctx.path
        assert os.path.basename(sent["path"]) == os.path.basename(ctx.path)
        assert b"<svg" in open(sent["path"], "rb").read()

    def test_the_copy_keeps_the_documents_own_file_name(self, monkeypatch, tmp_path):
        """The vault names the dataset from it, and /plm/state reads the part number back out."""
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        ctx = context(path="C:/drawings/DRW-000009-SVG.svg")
        copy = host.upload_copy(ctx.extension, ctx.path)
        assert os.path.basename(copy) == "DRW-000009-SVG.svg"

    def test_an_untouched_drawing_is_not_refused(self, monkeypatch, tmp_path):
        """The regression that drove the rewrite: this used to say "press Ctrl+S" forever."""
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        client = FakeClient()
        commands.save_to_plm(context(client))
        assert "save" in client.calls
        assert not any("Ctrl+S" in m for _s, m in client.said)

    def test_check_in_sends_the_same_copy(self, monkeypatch, tmp_path):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        monkeypatch.setattr(host.tempfile, "gettempdir", lambda: str(tmp_path))
        client = FakeClient()
        commands.check_in(context(client))
        assert "check_in" in client.calls


class TestValuesReachTheDrawing:
    def test_refresh_writes_what_the_service_returned(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(refresh_values={
            "success": True,
            "attribute_mappings": {"PartNumber": "DRW-000001-SVG", "Revision": "B"},
        })
        ctx = context(client)
        commands.refresh_values(ctx)
        assert svg.read_values(ctx.root) == {"PartNumber": "DRW-000001-SVG", "Revision": "B"}

    def test_edit_values_writes_only_when_the_dialog_was_saved(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(edit_values={
            "success": True, "saved": False,
            "attribute_mappings": {"Revision": "Z"},
        })
        ctx = context(client)
        commands.edit_values(ctx)
        assert svg.read_values(ctx.root) == {}

    def test_an_item_with_no_mapped_attributes_says_so(self, monkeypatch):
        """Otherwise it looks exactly like a command that silently did nothing."""
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(refresh_values={"success": True, "attribute_mappings": {}})
        commands.refresh_values(context(client))
        assert any("Nothing to update" in m for _s, m in client.said)


class TestRefusalsAreShown:
    def test_the_services_own_reason_is_what_the_user_reads(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(check_out={"success": False, "error": "Already checked out to jdoe."})
        commands.check_out(context(client))
        assert any("Already checked out to jdoe." in m for _s, m in client.said)

    def test_a_cancelled_dialog_says_nothing(self, monkeypatch):
        monkeypatch.setattr(commands.identity, "item_of", lambda client, path: "item-1")
        client = FakeClient(properties={"success": False, "cancelled": True})
        commands.properties(context(client))
        assert client.said == []


class TestRun:
    def test_an_unexpected_failure_becomes_a_sentence_not_a_traceback(self, monkeypatch):
        """Inkscape shows stderr in an error dialog, so a traceback reads as a broken add-in."""
        boom = lambda ctx: (_ for _ in ()).throw(ValueError("kaboom"))
        monkeypatch.setitem(commands.COMMANDS, "explode", boom)
        said = []
        monkeypatch.setattr(host, "say", lambda client, msg, severity="info": said.append(msg))
        commands.run("explode", FakeExtension())
        assert any("kaboom" in m for m in said)

    def test_an_unreachable_service_is_raised_for_the_entry_point_to_show(self, monkeypatch):
        """The one failure a toast cannot report: the thing that draws toasts is what is down."""
        def unreachable(ctx):
            raise ServiceUnavailable("no tray")
        monkeypatch.setitem(commands.COMMANDS, "unreachable", unreachable)
        with pytest.raises(ServiceUnavailable):
            commands.run("unreachable", FakeExtension())

    def test_an_unknown_command_does_nothing_quietly(self):
        commands.run("no-such-command", FakeExtension())
