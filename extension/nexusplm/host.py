"""The parts that know they are inside Inkscape.

Everything Inkscape-shaped lives here so the command bodies do not have to care: where the log
goes, what the open document's real path is, how to put a file in front of the user, and how to
say something to them.

Two Inkscape facts shape all of it, both measured on 1.4.2 rather than assumed:

* **An extension is handed a temporary copy of the document**, not the file. ``input_file`` was
  ``…\\Temp\\ink_ext_XXXXXX.svgPJRYV3`` while the document was
  ``…\\Temp\\nexus-probe-doc.svg``. The edited copy goes back to Inkscape on stdout. Writing the
  real path is how you lose the user's work, and ``inkex`` says so in capitals.
* **``DOCUMENT_PATH`` does give the real saved path**, so identity still works the way it does in
  every other host: the part number is read from the file name and the service resolves the item
  from it. An unsaved drawing has no path, and that is a state the commands must handle rather
  than a failure.
"""

import os
import tempfile
import subprocess
import sys

#: Beside every other Nexus add-in's log, under its own name so two hosts never share a file.
LOG_PATH = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"),
    "NexusPLM", "Logs", "plminkscapeaddin.log")

HELP_URL = "https://github.com/Nexus-PLM/Nexus.PLM.Inkscape.Addins"


def log(message):
    """A line in the shared log. Best effort - a command must not fail over a log write."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def document_path(extension):
    """The real, saved path of the drawing the extension was run on, or ``None``.

    ``None`` means the drawing has never been saved, which is a normal state and not an error:
    Save As New Item is exactly the command for it.

    ``inkex`` answers an empty string for "never saved" and ``None`` for "this Inkscape is too old
    to say". Both mean the same thing to us, and both become ``None`` here so a caller has one
    case to handle instead of three.
    """
    try:
        path = extension.document_path()
    except Exception:
        path = os.environ.get("DOCUMENT_PATH") or None
    return path or None


def open_document(path):
    """Show a file to the user in Inkscape.

    An extension cannot tell the Inkscape that is running to open something - there is no such
    call in the extension interface, which only speaks in the document it was handed. So a new
    Inkscape is started on the file. The running one keeps whatever the user had open, which is
    also the behaviour they want: opening an item from the vault should not close their work.
    """
    executable = inkscape_executable()
    if not executable:
        raise RuntimeError("Could not find inkscape.exe to open %s with." % path)

    # The new Inkscape must be launched so that it inherits NOTHING from this process. Both
    # halves below were paid for by a user-visible bug:
    #
    # 1. **DEVNULL on all three streams.** Inkscape reads an extension's stdout to get the
    #    modified document back, and waits for that pipe to close. A child holding the same
    #    handle keeps it open for as long as it lives, so Inkscape sat at "Not Responding" until
    #    the second window was closed. A plain os.spawnv inherits the handles and does exactly
    #    this - it was tried, and that is what happened.
    # 2. **Detached, with its own process group**, so closing the first Inkscape cannot take the
    #    second down with it.
    #
    # The Popen object itself is never reaped, which makes Python print "ResourceWarning:
    # subprocess N is still running" to stderr at shutdown - and Inkscape shows stderr in a
    # dialog. That is handled once, at the entry point, by silencing warnings: stderr is a user
    # interface here, not a developer channel.
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) \
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    subprocess.Popen(
        [executable, path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )


def inkscape_executable():
    """Where Inkscape itself is, found rather than configured.

    An extension runs under Inkscape's own bundled Python, so the interpreter is inside the
    installation and the executable is its sibling. That is true of every platform's layout and
    needs no setting, which matters because a hardcoded path is the thing that breaks on the one
    machine that installed somewhere else.
    """
    here = os.path.dirname(os.path.abspath(sys.executable))
    for candidate in (
        os.path.join(here, "inkscape.exe"),
        os.path.join(here, "inkscape"),
        os.path.join(os.path.dirname(here), "bin", "inkscape.exe"),
        os.path.join(os.path.dirname(here), "bin", "inkscape"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def open_url(url):
    """Open a page in the user's browser.

    ``webbrowser`` rather than ``os.startfile`` so this says the same thing on every platform, and
    because Inkscape's bundled Python has it - it is standard library.
    """
    import webbrowser
    webbrowser.open(url)


def say(client, message, severity="info"):
    """Tell the user something, through the one toast the tray host owns.

    An extension has no toast of its own, and printing to stderr would put the text in Inkscape's
    own error dialog - which is the wrong shape for "saved" and far too loud for it.
    """
    try:
        client.notify(message, severity)
    except Exception:
        log("could not post a notification: " + message)


def upload_copy(extension, path):
    """A file holding exactly the drawing the user is looking at, for PLM to take.

    Every other Nexus add-in saves the document and then uploads the file. Inkscape's extension
    interface has no save, so the first attempt here compared the file on disk with the document
    on screen and refused when they differed, telling the user to press Ctrl+S.

    **That was wrong, and driving it is what showed it.** Inkscape's in-memory document is never
    byte-identical to the file: it carries ``sodipodi:namedview``, its own ``inkscape:version``
    and other bookkeeping that only exists once the document is open. So the check fired on a
    drawing nobody had touched, and Save to PLM, Save As New and Check In would have refused for
    ever, each time blaming the user for an edit they had not made.

    There is nothing to compare, because there is no need to compare. Inkscape hands the extension
    the **current** document, unsaved edits included - so the honest thing to upload is that,
    not whatever the file happens to hold. The copy is written under the real document's own file
    name, because the vault names a dataset from it and ``/plm/state?file_path=`` reads the part
    number back out of it; a temp name would break both.
    """
    from lxml import etree

    folder = os.path.join(tempfile.gettempdir(), "nexus-inkscape")
    os.makedirs(folder, exist_ok=True)

    name = os.path.basename(path) if path else "Untitled.svg"
    copy = os.path.join(folder, name)
    # etree.tostring(element), not element.tostring() - an lxml Element has no such method, and
    # the first version of this called it and swallowed the AttributeError.
    with open(copy, "wb") as handle:
        handle.write(etree.tostring(extension.svg.getroottree().getroot(), xml_declaration=True,
                                    encoding="UTF-8"))
    return copy
