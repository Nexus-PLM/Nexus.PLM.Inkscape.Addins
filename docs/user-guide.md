# Nexus PLM for Inkscape — user guide

Everything is under **Extensions ▸ Nexus PLM**. Every dialog you see belongs to the Nexus PLM tray
application; the same dialogs appear in every other Nexus PLM add-in, so what you learn here holds
in GIMP, QGIS and the office suites too.

## Before you start

1. The **Nexus PLM tray application** must be running (the tray icon near the clock). If it is
   not, every command says so and stops.
2. **Sign In…** once. The session is shared by every Nexus add-in on the machine and is kept
   between Inkscape sessions; **Connection Status** tells you who is signed in.

## The drawing is the item

A drawing becomes a PLM item in one of three ways:

- **New from Template…** — pick a type, PLM numbers the item, and the type's template opens in a
  new Inkscape window with the part number, revision, description and dates already in it.
- **Open from PLM…** / **Search…** — browse or search the vault; the drawing you pick opens in a
  new window. Your current drawing is left alone.
- **Save As New Item…** — register the drawing you have open as a new item. **Save As Existing
  Item…** gives its content to an item that already exists instead.

From then on the add-in knows which item the file is, whichever way you open it.

## Working on an item

| Command | What it does |
|---|---|
| **Check Out** | Takes the lock. Nobody else can change the item while you hold it. |
| **Save to PLM** | Uploads the drawing *as it is on screen* as a new version of the revision. You keep the lock. The drawing's file is written at the same time, so the disk and the vault agree. |
| **Check In** | Uploads and releases the lock. You can leave a comment. |
| **Revise** | Starts the next revision — major (A → B) or minor (A → A.001), as the type allows. **The window you are in becomes the new revision**; the title block updates, nothing new opens. |
| **Change Ownership…** | Hands the item to another user. |
| **Properties…** | The item's full card: revisions, workflows, history, approvers, attachments. |
| **Edit Values…** | Edit the item's attributes. Values PLM owns are shown locked; the ones the drawing owns are editable. What you save is written into the drawing. |
| **Refresh Values** | Re-read the item's attributes from PLM into the drawing — after somebody else changed them, or after Revise. |
| **My Worklist…** / **New Workflow…** | What PLM is waiting on you for; start a workflow on this item (this is how a revision gets Released). |

## Where the values go

Every attribute the type maps is written **into the SVG file itself**, in the drawing's metadata.
You will not see it on the canvas and you do not need to: the file carries its part number and
revision wherever it goes, and PLM reads them back from it.

If the drawing has a **text object whose label is an attribute name** — `PartNumber`, `Revision`,
`Description`, `Author`, `Department`, `CreationDate` — the value is drawn into it too. The
template's title block is built this way. To add one to your own drawing: draw a text, open
**Object ▸ Object Properties**, and set its *Label* to the attribute name.

Inkscape marks the drawing modified after a Nexus command wrote values into it; save it (Ctrl+S)
when you are done, as you normally would.

## Session and information

**Sign In…** / **Sign Out** · **Current Settings…** (staging folder, service port, where the
service connects) · **Connection Status** (is the service up, who is signed in) · **Help** (this
project's page) · **About** (add-in and service versions).

## If something does not work

- *"Cannot reach Nexus PLM on http://localhost:5100"* — start the Nexus PLM tray application.
- *"This drawing is not registered in PLM"* — the file is not an item yet. Use **Save As New Item…**
  or open the item from PLM.
- *"Save this drawing to a file first"* — a never-saved drawing has no file for PLM to take.
- A command that PLM refuses (checked out to someone else, released revision) says so in PLM's own
  words in a toast.
- The add-in's log is `%APPDATA%\NexusPLM\Logs\plminkscapeaddin.log`.
