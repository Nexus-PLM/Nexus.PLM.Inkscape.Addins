# Nexus PLM for Inkscape

Product lifecycle management from inside Inkscape. A Python extension that puts the same command
set the Nexus PLM add-ins give Word, LibreOffice, OpenOffice and ONLYOFFICE into
**Extensions ▸ Nexus PLM**.

Twenty-one commands: sign in and out, create from a template, open and search the vault, save,
save as a new or an existing item, check out and in, revise, change ownership, worklist and
workflow, properties, edit and refresh attribute values, settings, connection status, help and
about.

Tested against Inkscape **1.4.2** (bundled Python 3.12).

---

## How it fits together

The extension talks to **one** thing: the Nexus PLM Addin Service on `http://localhost:5100`,
carried by the Nexus PLM tray application. It never reaches the Engine or the vault itself. The
service owns the session, the dialogs and the toasts, so this add-in is thin by design — it knows
about SVG and about Inkscape, and nothing else.

```
Inkscape  ──►  nexus_plm.py  ──►  nexusplm/commands.py  ──►  Addin Service (localhost:5100)
                                        │                            │
                                   nexusplm/svg.py            the tray's dialogs and toasts
                                   (values in the drawing)
```

`client.py`, `state.py`, `identity.py` and `navigator.py` are shared with the LibreOffice add-in
and carry no Inkscape API at all.

## Where a PLM value lives in a drawing

Two places, and both matter:

| | Where | Why |
|---|---|---|
| The record | `<metadata>` → `<nexus:attributes>` | Every value, whether or not the drawing shows it. Survives a round trip because Inkscape preserves foreign namespaces in `<metadata>`. |
| The visible half | a `<text>` whose `inkscape:label` is the attribute key | A value nobody can see is a value nobody believes is there. Optional per drawing. |

Label a text element `PartNumber` and the part number is drawn into it. Label nothing and the
values are still recorded.

## Three things Inkscape does differently

All measured on 1.4.2, not assumed — and each one shaped the design.

**An extension is handed a copy, not the file.** `input_file` is a temporary
`ink_ext_XXXXXX.svg…`; the edited result goes back to Inkscape on stdout. `inkex` warns in
capitals against reading or writing the real path, because Inkscape has not necessarily flushed
its changes and will not respect yours.

**`DOCUMENT_PATH` does give the real saved path**, so identity works as in every other host: the
part number is read from the file name and the service resolves the item from it.

**An extension cannot save the document.** There is no such call. So nothing here uploads the file
on disk — every command that gives PLM a file gives it the drawing *as it is on screen*, written
to a temp copy under the document's own name. The first version compared disk with screen and
refused when they differed; that fired on a drawing nobody had touched, because Inkscape's
in-memory document always carries `sodipodi:namedview` and its own version stamp. Driving it is
what showed that.

## Building and installing

```bash
cd extension
python build.py              # regenerate the .inx files from the menu table
python build.py --install    # ...and copy into Inkscape's user extensions directory
```

The `.inx` files are **generated**. Edit `MENU` in `build.py`, not the XML.

## Tests

```bash
python -m pytest tests/ -q
```

They need `lxml` and `pytest` and run without Inkscape — 40 of them, covering where values live,
what gets uploaded, every refusal path, and a guard that the menu and the command table still
agree.

## Licence

MIT. See [LICENSE](LICENSE).
