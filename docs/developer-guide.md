# Nexus PLM for Inkscape — developer guide

How the extension is built, how to change it safely, and what Inkscape does differently. Every
"measured" fact below was measured on Inkscape 1.4.2 and cost something to learn.

## Architecture in one paragraph

Inkscape runs an extension as a **separate process** per invocation: it reads an `.inx` file to
know what to show in the menu and what script to run, hands the script a **temporary copy** of the
document, and takes the modified document back on **stdout**. This add-in has one script,
`extension/nexus_plm.py`, and twenty-one `.inx` files that each run it with a different
`--command`. The script builds a `Context` (service client, the document, its real path from
`DOCUMENT_PATH`) and calls the matching function in `nexusplm/commands.py`. Everything that talks
HTTP is in `nexusplm/client.py`; everything that touches the SVG is in `nexusplm/svg.py`;
everything that knows it is inside Inkscape is in `nexusplm/host.py`. Nothing else imports
`inkex`, which is why 74 tests run under plain Python.

```
extension/
  nexus_plm.py          entry point: parse --command, build Context, run; turns ServiceUnavailable
                        into the "tray is not running" dialog
  build.py              MENU table → .inx files; --install copies into %APPDATA%\inkscape\extensions
  nexus_plm_*.inx       GENERATED. Never hand-edit.
  nexusplm/
    commands.py         one function per command; Context; COMMANDS dispatch; run()
    svg.py              read_values / write_values / offerable_values / write_into_file / for_display
    host.py             document_path / upload_copy / same_file / replace_document / open_document / say / log
    client.py           Client: one method per service endpoint (shared with GIMP and QGIS)
    state.py            the path → item map, %APPDATA%\NexusPLM\inkscape-documents.json (shared)
    identity.py         which item a file is: the map first, then /plm/state (shared)
    navigator.py        folder tree shaping (shared)
tools/build_template.py  makes dist/Inkscape Drawing.svg
tests/                   test_commands, test_svg, test_host, test_installer
installer/               Inno Setup script
```

## The one rule everything follows

**The extension talks only to the Addin Service** (`http://localhost:5100`), never to the Engine
or the vault. The service owns the session, every dialog and every toast, and it enumerates no
hosts: this add-in declares `HOST_NAME = "Inkscape"` and `FILE_EXTENSIONS = ".svg;.svgz"` with
each request. If a change here seems to need a service change, stop — it usually means the add-in
should be declaring something instead.

## The record

`svg.py` keeps PLM's values in the drawing's own `<metadata>`:

```xml
<metadata>
  <nexus:attributes xmlns:nexus="https://nexusplm.com/ns/plm">
    <nexus:value key="PartNumber">IND-00000005-SVG</nexus:value>
    <nexus:value key="Revision">C</nexus:value>
    …
```

Inkscape preserves foreign namespaces in `<metadata>` through a save, so the record travels with
the file. `write_values(root, values)` also draws any value the drawing is set up to show — a
`<text>` whose `inkscape:label` is the key — replacing the text inside its first `<tspan>` (setting
the `<text>`'s own text would leave the old span underneath). It returns `(recorded, shown)` and
callers log both, so a user hunting for a value the drawing never displayed is told the record has
it.

`write_into_file(path, values)` does the same to a **file nothing has open** (`.svg` or `.svgz`),
with lxml alone — this is how New from Template and Open from PLM fill a staged file before
Inkscape opens it.

`offerable_values(root)` is what Save As New offers the service as the new item's defaults: only
filled-in values, and never the server's own keys (part number, revision, the four stamps). The
service merges the offer onto the new revision as-is, and a template's blank slots once wiped
`createdBy` and `creationDate` to `""`.

## The command shape

Every command is `def name(context)` and returns `None`. The pattern:

```python
def check_in(context):
    item_id = _require_item(context)          # tells the user if the file is not an item
    if item_id is None:
        return
    answer = context.client.check_in(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Check In")  # PLM's own words, via a toast
```

- `_to_upload` writes Inkscape's **current buffer** to the document's **own path** and returns
  that path (`host.upload_copy`). Not a temp copy: `SaveRequest.FilePath` is one path the service
  both reads and records as `plm_file_path`, so a temp path became the next revision's home.
- `_hand_over(context, answer)` takes a staged file: remembers which item it is, writes the values
  into the file, then either **replaces the open document** with it (when it is the file already
  open — Revise) or opens it in a new Inkscape.
- `_apply(context, answer)` writes returned `attribute_mappings` into the open drawing.
- `run(name, extension)` wraps it all: logs start/done, turns any exception into a toast, and lets
  only `ServiceUnavailable` escape for the entry point to show as a dialog.

### Adding a command

1. Add `("my-command", "My Command...")` to `MENU` in `build.py`.
2. Add `def my_command(context)` in `commands.py` and register it in `COMMANDS`.
3. If the service has no endpoint for it yet, add the method to `client.py` — request shapes come
   from the service's `PlmModels.cs`, not from guessing.
4. `python build.py --install`; Inkscape picks up a new `.inx` without a restart.
5. Tests: `TestTheMenuAndTheCommandsAgree` fails until the table and the dispatch agree.

## Things Inkscape does differently (all measured)

| | Consequence |
|---|---|
| The extension gets a temp copy; the result goes back on stdout. | Never read the real path for content; `DOCUMENT_PATH` is the real path for identity. |
| There is no "save" call. | `upload_copy` writes Inkscape's own buffer to the real path. Inkscape 1.4 does not watch the file; the window stays marked modified. |
| inkex emits `self.document` on exit; `has_changed` calls `etree.tostring` on it first. | To replace the open document hand inkex a tree from `inkex.load_svg`, never bytes — bytes are dropped silently. |
| `needs-document="false"` crashes inkex's loader. | Every `.inx` needs a document; a test holds it. |
| stderr is shown in a dialog. | `warnings.simplefilter("ignore")` at the entry point; a Popen child must not inherit stdout. |
| Inkscape draws a "working…" window while an effect runs. | `implements-custom-gui="true"` on `<effect>`. |
| A submenu is sorted alphabetically. | The order of `MENU` is documentation only. |
| `inkscape.exe file` from a shell joins the running instance; from the extension's detached Popen it starts a new process. | One drawing per process is the proven case. |

## Running the tests

```bash
python -m pytest tests/ -q
```

The fixtures patch `host.LOG_PATH`, `host.open_document`, `host.open_url` and `state._PATH`, so no
test writes the user's real log or document map or starts an Inkscape. A test that leaves a line
in a real diagnostic will mislead somebody at the worst moment — one did.

## The server side

A type that hands out SVG templates needs, on the Engine: a MIME row (`svg` →
`image/svg+xml`, `.svg,.svgz`), a numbering scheme (`InkscapeDrawing` → `IND-########-SVG`), the
type itself (`n5InkscapeDrawing`, cloned from a document type with the standard twelve connector
mappings), and the template uploaded to the vault and attached to the type. All of it goes through
the API (`/api/mimetypes/{id}`, `/api/numberschemas`, `/api/types`, the vault's `/api/vault/upload`)
and `POST /api/types` hot-registers — no restart. The template is made by
`tools/build_template.py`: an A4 sheet with a title block of labelled text objects and empty
record slots.

## Building the installer

```
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\Nexus.PLM.Inkscape.Addin.iss
```

Per user, no elevation, into `%APPDATA%\inkscape\extensions`. `tests/test_installer.py` holds the
script against the source: `AppVersion` == `commands.VERSION`, the destination == `build.py`'s,
every `[Files]` source exists, every menu entry has an `.inx`, uninstall removes only what was
installed. Bump `VERSION` and `AppVersion` together.

## Debugging

- Add-in log: `%APPDATA%\NexusPLM\Logs\plminkscapeaddin.log` — one line per command start/done,
  plus what was written where.
- Document map: `%APPDATA%\NexusPLM\inkscape-documents.json`.
- Is the tray signed in? `curl http://localhost:5100/api/auth/me`.
- What does PLM think a file is? `curl "http://localhost:5100/plm/state?file_path=C:\Nexus\Staging\IND-00000005-SVG.svg"`.
