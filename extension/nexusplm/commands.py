"""What each Nexus PLM menu entry does, in one place and with no Inkscape API in sight.

Every command takes a :class:`Context` and returns ``None``. The context carries the four things a
command can need - the service client, the drawing's tree, its real path, and the window to parent
a dialog to - so no command has to go and find them, and so all of this can be tested without
Inkscape running.

**The one place Inkscape differs from the office add-ins**, and it is worth stating plainly: an
extension cannot save the document. Word, LibreOffice and OpenOffice all save the document and
then upload the file, because their object models let them. Inkscape's does not - it hands the
extension a copy and takes the result back.

So nothing here uploads ``context.path``. Every command that gives PLM a file gives it
:func:`_to_upload`, which is the drawing **as it is on screen**, unsaved edits included. That is
both simpler and more truthful than uploading whatever the disk happens to hold, and it avoids the
trap the first version fell into - see :func:`nexusplm.host.upload_copy`.
"""

from nexusplm import host
from nexusplm import identity
from nexusplm import state
from nexusplm import svg
from nexusplm.client import Client, ServiceUnavailable, FILE_EXTENSIONS


class Context(object):
    """What a command is given. Built once by the entry point."""

    def __init__(self, client, extension, path, hwnd=0):
        self.client = client
        self.extension = extension
        self.path = path
        self.hwnd = hwnd

    @property
    def root(self):
        """The drawing's root element - changes to it go back to Inkscape."""
        return self.extension.svg.getroottree().getroot()


# ── shared helpers ───────────────────────────────────────────────────────────

def _refused(context, answer, command):
    """Show the service's own reason for refusing. A cancelled dialog is not a refusal."""
    if answer.get("cancelled"):
        return
    host.say(context.client,
             answer.get("error") or "Nexus PLM did not answer the %s request." % command,
             "warning")


def _require_path(context):
    """The drawing must have been saved before PLM can do anything with the file itself."""
    if context.path:
        return True
    host.say(context.client,
             "Save this drawing to a file first. Nexus PLM works on the saved file, and this one "
             "has never been saved.", "warning")
    return False


def _require_item(context):
    """The item this drawing is, or ``None`` with the user already told why not."""
    if not _require_path(context):
        return None
    item_id = identity.item_of(context.client, context.path)
    if item_id is None:
        host.say(context.client, "This drawing is not registered in PLM.", "warning")
    return item_id


def _to_upload(context):
    """The file PLM should take: the drawing as it is on screen, not as the disk last saw it.

    See :func:`nexusplm.host.upload_copy` for why this is a copy and not ``context.path``.
    """
    return host.upload_copy(context.extension, context.path)


def _remember(context, answer):
    """Write down that this file is that item - the next command reads it back.

    Through ``identity.remember`` rather than ``state.remember`` directly, because the service
    does not use one name for the item across every endpoint: ``/plm/new`` answers
    ``plm_object_id`` where others answer ``item_id``. identity knows both. Reaching past it to
    state was how New from Template created an item and then wrote nothing down.
    """
    identity.remember(context.path, answer)


def _hand_over(context, answer):
    """Take the file PLM just staged: remember it, fill in its values, and show it.

    The order matters. The values go in while the drawing is still only a file - once Inkscape
    has it open, writing the path is forbidden and pointless. Without this step New from Template
    opens a drawing whose title block still reads "-" for an item PLM has just numbered.
    """
    staged = answer.get("file_path")
    if not staged:
        return False

    identity.remember(staged, answer)

    mappings = answer.get("attribute_mappings") or {}
    if mappings:
        try:
            recorded, drawn = svg.write_into_file(staged, mappings)
            host.log("staged %s: wrote %d value(s), %d shown" % (staged, recorded, drawn))
        except Exception as error:                              # noqa: BLE001
            # A drawing that opens without its values is worth having; a command that fails
            # because it could not fill them in is not.
            host.log("could not write values into %s: %r" % (staged, error))

    if host.same_file(staged, context.path):
        # PLM staged the file the user already has open - which is what Revise does, since the
        # next revision keeps the part number and so the file name. Hand it back as this
        # extension's output and the open window BECOMES the new revision. Opening it in a
        # second Inkscape was the bug Marc saw: "opening a new file, not up-revving the
        # existing one", with the closed revision still open beside it.
        host.replace_document(context.extension, staged)
        host.log("replaced the open drawing with %s" % staged)
    else:
        host.open_document(staged)
    return True


def _apply(context, answer, quiet=False):
    """Write the attribute values the service returned into the drawing."""
    mappings = answer.get("attribute_mappings") or {}
    recorded, drawn = svg.write_values(context.root, mappings)
    if recorded:
        host.log("wrote %d value(s), %d shown on the drawing" % (recorded, drawn))
    elif not quiet:
        host.say(context.client,
                 "Nothing to update: this item has no attributes mapped into the drawing.")
    return recorded


# ── account ──────────────────────────────────────────────────────────────────

def sign_in(context):
    """Sign in, through the service's own window."""
    answer = context.client.sign_in(context.hwnd)
    if not answer.get("success"):
        _refused(context, answer, "Sign In")


def sign_out(context):
    """Sign out of PLM.

    No toast of our own on success. ``/api/auth/logout`` carries the service's ``[CommandToast]``,
    so the tray has already said "Logout - Signed out admin" by the time the answer arrives; a
    second "Signed out." underneath it is what driving showed. The Office add-ins had the same
    double-toast on Settings for the same reason - the service announces its own commands.
    """
    answer = context.client.sign_out()
    if not answer.get("success"):
        _refused(context, answer, "Sign Out")


# ── data management ──────────────────────────────────────────────────────────

def new_from_template(context):
    """Create a new item from a type's template and open the drawing it makes."""
    answer = context.client.new(context.hwnd, file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "New")

    if not _hand_over(context, answer):
        host.say(context.client,
                 "PLM created the item but did not stage a file to open.", "warning")


def open_from_plm(context):
    """Browse the vault and open the chosen drawing."""
    answer = context.client.open_document(context.hwnd, file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "Open")

    if not _hand_over(context, answer):
        _refused(context, answer, "Open")


def search(context):
    """Search PLM, and open whatever the user picks."""
    answer = context.client.search(context.hwnd)
    if not answer.get("success"):
        return _refused(context, answer, "Search")
    _hand_over(context, answer)


def save_to_plm(context):
    """Upload this drawing to its item, keeping the lock."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.save(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Save")


def save_as_new(context):
    """Register this drawing as a new PLM item."""
    if not _require_path(context):
        return

    answer = context.client.save_as_new(
        _to_upload(context), context.hwnd,
        attributes=svg.read_values(context.root),
        file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "Save As New Item")

    # Registering and then not writing it down is how a drawing PLM had just created came back
    # as "not registered in PLM" on the very next command.
    _remember(context, answer)
    _apply(context, answer, quiet=True)


def save_as_existing(context):
    """Give this drawing's content to an item that already exists."""
    if not _require_path(context):
        return

    answer = context.client.save_as_existing(
        _to_upload(context), context.hwnd, file_extensions=FILE_EXTENSIONS)
    if not answer.get("success"):
        return _refused(context, answer, "Save As Existing Item")
    _remember(context, answer)
    _apply(context, answer, quiet=True)


# ── lifecycle ────────────────────────────────────────────────────────────────

def check_out(context):
    """Take the lock, so nobody else can change the item while you work."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.check_out(item_id)
    if not answer.get("success"):
        _refused(context, answer, "Check Out")


def check_in(context):
    """Upload and release the lock."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.check_in(item_id, _to_upload(context))
    if not answer.get("success"):
        _refused(context, answer, "Check In")


def revise(context):
    """Start a new revision of this item."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.revise(item_id, context.hwnd)
    if not answer.get("success"):
        return _refused(context, answer, "Revise")

    _hand_over(context, answer)


def change_owner(context):
    """Hand the item to someone else."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.change_owner(item_id, context.hwnd, context.path)
    if not answer.get("success"):
        _refused(context, answer, "Change Ownership")


# ── workflow ─────────────────────────────────────────────────────────────────

def worklist(context):
    """Show what PLM is waiting on you for."""
    answer = context.client.worklist(context.hwnd)
    if not answer.get("success"):
        _refused(context, answer, "My Worklist")


def new_workflow(context):
    """Start a workflow on this item."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.new_workflow(item_id)
    if not answer.get("success"):
        _refused(context, answer, "New Workflow")


# ── attributes ───────────────────────────────────────────────────────────────

def properties(context):
    """Show the item's full card."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.properties(item_id, context.hwnd)
    if not answer.get("success"):
        _refused(context, answer, "Properties")


def edit_values(context):
    """Edit the item's attributes, then write what was saved back into the drawing."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.edit_values(item_id, context.hwnd, svg.read_values(context.root))
    if not answer.get("success"):
        return _refused(context, answer, "Edit Values")
    if answer.get("saved"):
        _apply(context, answer)


def refresh_values(context):
    """Re-read the item's attributes from PLM into the drawing."""
    item_id = _require_item(context)
    if item_id is None:
        return
    answer = context.client.refresh_values(item_id)
    if not answer.get("success"):
        return _refused(context, answer, "Refresh Values")
    _apply(context, answer)


# ── information ──────────────────────────────────────────────────────────────

def settings(context):
    """The service's own settings window."""
    answer = context.client.settings()
    if not answer.get("success"):
        _refused(context, answer, "Settings")


def about(context):
    """What this add-in and the service are."""
    answer = context.client.about(context.hwnd, addin_version=VERSION)
    if not answer.get("success"):
        _refused(context, answer, "About")


def help_site(context):
    """Open the add-in's documentation."""
    host.open_url(HELP_URL)


def connection_status(context):
    """Say whether the service is reachable, and who is signed in.

    ``health()`` first, and deliberately: it raises when the service is not running, which is the
    one answer this command exists to give. The field really is ``username`` - the SDK once looked
    for one the service never sends and reported every signed-in session as signed out.
    """
    context.client.health()
    who = context.client.me()
    if who.get("success"):
        host.say(context.client,
                 "Connected to Nexus PLM. Signed in as %s." % (who.get("username") or "you"))
    else:
        host.say(context.client, "Connected to Nexus PLM. Nobody is signed in.")


#: Add-in version, reported by About and in the service's log.
VERSION = "0.1.0"
HELP_URL = host.HELP_URL

#: Every command the menu can run, by the name its ``.inx`` passes.
COMMANDS = {
    "sign-in": sign_in,
    "sign-out": sign_out,
    "new-from-template": new_from_template,
    "open-from-plm": open_from_plm,
    "search": search,
    "save-to-plm": save_to_plm,
    "save-as-new": save_as_new,
    "save-as-existing": save_as_existing,
    "check-out": check_out,
    "check-in": check_in,
    "revise": revise,
    "change-owner": change_owner,
    "worklist": worklist,
    "new-workflow": new_workflow,
    "properties": properties,
    "edit-values": edit_values,
    "refresh-values": refresh_values,
    "settings": settings,
    "about": about,
    "help": help_site,
    "connection-status": connection_status,
}


def run(name, extension):
    """Run one command by name, turning every failure into something the user can read.

    A command must never leave a Python traceback in front of the user: Inkscape shows an
    extension's stderr in an error dialog, which turns a service that is merely not running into
    something that looks like a broken add-in.
    """
    client = Client()
    path = host.document_path(extension)
    context = Context(client, extension, path, hwnd=0)

    command = COMMANDS.get(name)
    if command is None:
        host.log("unknown command: %s" % name)
        return

    host.log("%s: started" % name)
    try:
        command(context)
        host.log("%s: done" % name)
    except ServiceUnavailable:
        # The one failure the user has to fix themselves, and the one they cannot be told about
        # by a toast - the thing that draws the toast is the thing that is not running.
        host.log("%s: the Nexus PLM tray application is not running" % name)
        raise
    except Exception as error:                                   # noqa: BLE001 - see docstring
        host.log("%s: failed: %r" % (name, error))
        host.say(client, "Nexus PLM could not complete %s: %s" % (name, error), "warning")
