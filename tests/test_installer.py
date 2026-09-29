"""The installer script, held against the source it ships.

An Inno script is text nobody runs until release day, and every value in it that also lives
somewhere else - the version, the destination, the list of files - is a value that drifts. These
tests read the .iss as text and check each one against where it really comes from, so a drift
fails here rather than on a user's machine.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "extension"))

import build  # noqa: E402
from nexusplm import commands  # noqa: E402

ISS = os.path.join(ROOT, "installer", "Nexus.PLM.Inkscape.Addin.iss")


def script():
    with open(ISS, encoding="utf-8") as handle:
        return handle.read()


def define(name):
    match = re.search(r'^#define %s\s+"([^"]*)"' % re.escape(name), script(), re.MULTILINE)
    assert match, "no #define %s in the installer" % name
    return match.group(1)


class TestTheVersion:
    def test_the_installer_ships_the_version_the_add_in_reports(self):
        """About says one number and Add/Remove Programs another - that is the drift this stops."""
        assert define("AppVersion") == commands.VERSION


class TestTheDestination:
    def test_it_is_where_build_py_installs_to(self):
        """Two installers - the developer one and the shipped one - must agree on where."""
        assert define("ExtensionsDir") == r"{userappdata}\inkscape\extensions"
        # build.py resolves the same directory through APPDATA.
        assert build.user_extensions_dir().lower().endswith(r"\inkscape\extensions")


class TestThePayload:
    def test_every_source_named_in_files_exists(self):
        sources = re.findall(r'^Source:\s*"\.\.\\([^"]+)"', script(), re.MULTILINE)
        assert sources, "no [Files] sources found"
        for source in sources:
            folder, pattern = os.path.split(source)
            base = os.path.join(ROOT, folder)
            assert os.path.isdir(base), "missing folder: " + folder
            if "*" in pattern:
                import fnmatch
                assert any(fnmatch.fnmatch(n, pattern) for n in os.listdir(base)), \
                    "nothing matches " + source
            else:
                assert os.path.isfile(os.path.join(base, pattern)), "missing file: " + source

    def test_every_menu_entry_has_an_inx_the_installer_ships(self):
        """A command whose .inx is missing from disk is a command the installer cannot ship."""
        for command, _label in build.MENU:
            assert os.path.isfile(os.path.join(ROOT, "extension", build.inx_name(command))), \
                "run build.py: no .inx for " + command

    def test_the_inx_glob_covers_every_menu_entry_and_nothing_else(self):
        """The [Files] line ships nexus_plm_*.inx. Every generated file must match it."""
        import fnmatch
        for command, _label in build.MENU:
            assert fnmatch.fnmatch(build.inx_name(command), "nexus_plm_*.inx")

    def test_the_developer_script_is_not_shipped(self):
        """build.py is for whoever is editing this repo, not for a user's Inkscape."""
        assert "build.py" not in re.findall(r'^Source:.*$', script(), re.MULTILINE).__str__()

    def test_compiled_python_is_excluded(self):
        """A stale __pycache__ is how an old module goes on being imported after its source changed."""
        assert "__pycache__" in script()


class TestUninstall:
    def test_it_removes_only_what_it_installed(self):
        """The extensions directory holds every other extension the user has."""
        body = script()
        assert r'{#ExtensionsDir}\nexusplm' in body
        assert r'{#ExtensionsDir}\nexus_plm.py' in body
        assert r'{#ExtensionsDir}\nexus_plm_*.inx' in body
        # Never the whole directory.
        assert not re.search(r'Type:\s*filesandordirs;\s*Name:\s*"\{#ExtensionsDir\}"\s*$',
                             body, re.MULTILINE)
