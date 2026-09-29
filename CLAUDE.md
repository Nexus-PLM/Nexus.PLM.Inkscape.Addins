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
- **Never read or write the document's real path**, except a freshly staged file nothing has open
  yet (`svg.write_into_file`). Inkscape hands over a copy and takes the
  result back on stdout. `inkex` says so in capitals, and writing it loses the user's work.
- **Uploads send the drawing on screen**, via `host.upload_copy`, never `context.path`. The copy
  keeps the document's own file name, because the vault names the dataset from it and
  `/plm/state?file_path=` reads the part number back out of it.
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
- Inkscape's in-memory document is never byte-identical to its file, so "has it changed?" cannot
  be answered by comparing them.

## Still to do

- No types or templates exist for SVG on the server, so New from Template has nothing to offer.
- Only Connection Status, Sign In and Save As New have been driven end to end.
- No installer: `build.py --install` is a developer script, and nothing user-facing may depend on
  one.
