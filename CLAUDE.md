# CLAUDE.md — Nexus.PLM.Inkscape.Addins

The Nexus PLM add-in for Inkscape: a Python extension under **Extensions ▸ Nexus PLM**.

---

## Layout

```
extension/
  nexus_plm.py          entry point - every .inx runs this with a different --command
  build.py              generates the .inx files from MENU, and installs
  nexusplm/
    client.py           HTTP to the Addin Service      ] shared with the LibreOffice
    state.py            path -> item map               ] add-in; no Inkscape API in
    identity.py         which item a file is           ] any of them
    navigator.py        folder tree shaping            ]
    svg.py              where a PLM value lives in a drawing
    host.py             the parts that know they are inside Inkscape
    commands.py         what each menu entry does
tests/                  pytest, runs without Inkscape
```

## Build

```bash
cd extension && python build.py --install
python -m pytest tests/ -q
```

`.inx` files are **generated**. Change `MENU` in `build.py`; never hand-edit the XML.

## Rules that are not negotiable

- **The metadata record is the deliverable.** Attributes are injected into the file's own data
  model so the SVG carries them wherever it goes. Drawing values into labelled text elements is a
  convenience most users will not use - never let it become the thing a command depends on.
- **Never read the document's real path for content** - Inkscape hands over a copy and takes the
  result back on stdout; the file on disk is stale the moment the user draws. The two writes that
  are allowed: a freshly staged file nothing has open yet (`svg.write_into_file`), and
  `host.upload_copy`, which writes Inkscape's own current buffer over the document's path.
- **Uploads send the drawing on screen, written to the document's OWN path**, via
  `host.upload_copy`. Not a temp copy: `SaveRequest` has one `FilePath` that the service both reads
  and records as the item's `plm_file_path`, so a temp path became the next revision's home -
  Revise staged rev B under `%TEMP%` and opened it in a second window. Marc: "it must get written
  to the staging directory."
- **Revise ups the revision in place.** When the staged file *is* the open document
  (`host.same_file`), `_hand_over` makes it the extension's output (`host.replace_document`)
  instead of launching a second Inkscape. A different file - Open from PLM, Search - still opens
  in a new window.
- **No `needs-document="false"`.** An `EffectExtension` with no document dies inside inkex's own
  loader (`'NoneType' object has no attribute 'selection'`) and Inkscape shows the traceback to
  the user. A test holds this.
- **Standard library only** in `nexusplm/`, plus `lxml`, which Inkscape bundles. We do not control
  what is installed in Inkscape's Python; `requests` is not there.
- **The service is the only thing this talks to.** Never the Engine, never the vault.
- **A command never leaves a traceback in front of the user.** Inkscape shows stderr in an error
  dialog, so an unhandled exception reads as a broken add-in. `commands.run` turns anything
  unexpected into a toast; only `ServiceUnavailable` escapes, and the entry point turns that into
  the "tray is not running" dialog.
- Anything host-specific is **declared by the add-in** (`HOST_NAME`, `FILE_EXTENSIONS`) and
  travels with the request. The service keeps no list of hosts, and must need no change for this
  one. If something here seems to need a service change, stop and ask what it should be declaring
  instead.

## Measured facts worth not re-learning

- Inkscape **sorts a submenu's entries alphabetically**. The order of `MENU` is documentation.
- `DOCUMENT_PATH` holds the real saved path; `input_file` is a temp copy.
- Inkscape picks up a new `.inx` **without a restart**.
- Inkscape 1.4 does **not watch the document's file**: writing it from an extension neither
  reloads the drawing nor prompts. The window stays marked modified.
- The service's `[CommandToast]` commands (Sign Out among them) already toast; a toast of our
  own on top is a double.
- Inkscape's in-memory document is never byte-identical to its file, so "has it changed?" cannot
  be answered by comparing them.

## Installer

`installer/Nexus.PLM.Inkscape.Addin.iss` - Inno Setup, per-user, no elevation. Compile with
ISCC; `tests/test_installer.py` holds it against the source (version, destination, every payload
file, every menu entry's .inx, uninstall scope). It installs into `%APPDATA%\inkscape\extensions`.
`build.py --install` remains the developer path, and is not shipped.

## Still to do

- **All 21 commands driven end to end on the installed extension (29 Sep 2026)**, after four fixes
  the sweep found: upload to the document's own path, Revise in place, offer only real values on
  Save As New, silent Sign Out + filled sheet after Save As Existing. Service-side observations
  from the sweep are in PR #8.
- Attributes do not survive **export** to PNG. XMP would; nobody has asked.

## Measured while driving

- `inkscape.exe <file>` from a shell **joins the running Inkscape** as a second window in the same
  process; the extension's detached `Popen` launch does not (a separate process every time). With
  two windows in one process, an effect run from the second window retitled and resized the first -
  Inkscape's own document swap, not ours. One drawing per process is the case that is proven.
- After Save to PLM the window stays marked modified: Inkscape 1.4 does not watch its file.
- Inkscape sometimes un-maximises a window after an effect replaces its document. Cosmetic.
