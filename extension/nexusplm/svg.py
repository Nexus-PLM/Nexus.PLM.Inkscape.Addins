"""Where a PLM value lives inside an SVG, and how it is read back.

Two places, for the same reason LibreOffice writes both document properties and named shapes:

* **``<metadata>``** holds every value, whether or not the drawing shows it. This is the record,
  and it survives a round trip through Inkscape untouched because Inkscape preserves foreign
  namespaces inside ``<metadata>`` rather than discarding them.
* **A text element labelled with the attribute's key** shows the value on the canvas. This is the
  half a person can see. It is optional per drawing: a template that wants the part number drawn
  on it labels a text element ``PartNumber``; one that does not, does not, and nothing is written
  there.

The Impress work settled the principle - a value the user cannot see on the page is a value they
do not believe is there - so the visible half is not a nicety.

**Nothing here writes a file.** Inkscape hands an extension a *copy* of the document and takes the
result back on stdout; writing the real path behind its back loses data, and ``inkex`` says so in
capitals. So these functions take and change an lxml tree, and Inkscape does the saving.
"""

import copy

#: Our own namespace for the record half. Deliberately not Dublin Core: ``dc:title`` and friends
#: are a fixed vocabulary and PLM attributes are whatever the type declares, so borrowing DC would
#: mean inventing a mapping and losing every attribute that did not fit one.
NEXUS_NS = "https://nexusplm.com/ns/plm"
SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

_METADATA = "{%s}metadata" % SVG_NS
_ATTRIBUTES = "{%s}attributes" % NEXUS_NS
_VALUE = "{%s}value" % NEXUS_NS
_TEXT = "{%s}text" % SVG_NS
_TSPAN = "{%s}tspan" % SVG_NS
_LABEL = "{%s}label" % INKSCAPE_NS

#: The identity keys the add-in owns. They are written like any other value, but they are the ones
#: a command needs back, so they are named rather than left to chance.
PART_NUMBER = "PartNumber"
REVISION = "Revision"
DESCRIPTION = "Description"


def _metadata_of(root, create=False):
    """The document's ``<metadata>`` element, optionally created if absent."""
    found = root.find(_METADATA)
    if found is None and create:
        found = root.makeelement(_METADATA, {})
        # First child: where Inkscape itself puts it, and where a person looking at the XML
        # expects the document's description of itself to be.
        root.insert(0, found)
    return found


def _attributes_of(root, create=False):
    """Our ``<nexus:attributes>`` block inside ``<metadata>``."""
    metadata = _metadata_of(root, create=create)
    if metadata is None:
        return None
    found = metadata.find(_ATTRIBUTES)
    if found is None and create:
        found = metadata.makeelement(_ATTRIBUTES, {})
        metadata.append(found)
    return found


def read_values(root):
    """Every PLM value recorded in the drawing, as ``{key: text}``.

    An absent metadata block is not an error - it is a drawing that has never been in PLM - and
    answers an empty dict.
    """
    block = _attributes_of(root)
    if block is None:
        return {}

    values = {}
    for element in block.findall(_VALUE):
        key = element.get("key")
        if key:
            values[key] = element.text or ""
    return values


#: Keys PLM stamps itself. A drawing's copies of them are never offered back as the values of a
#: new item. Save As New merges whatever a caller offers straight onto the new revision (only
#: ``plm_`` keys are refused), so a drawing copied from IND-00000004 would hand the new item its
#: old part number, and a template's empty record wiped ``createdBy`` and ``creationDate`` to ""
#: - measured on IND-00000007-SVG, 29 Sep 2026: every value came back blank and the title block
#: emptied.
SYSTEM_KEYS = frozenset(k.lower() for k in (
    "PartNumber", "Revision", "CreatedBy", "CreationDate", "ModifiedBy", "ModificationDate"))


def offerable_values(root):
    """The drawing's values a new item may take as defaults: filled in, and not PLM's own.

    An empty ``<nexus:value>`` is a slot the template left for PLM to fill, not a value of "";
    offering it as "" is how the blanks above were written. And the identity and stamp keys belong
    to the server whatever the drawing says.
    """
    return {key: value for key, value in read_values(root).items()
            if value and key.lower() not in SYSTEM_KEYS}


def write_values(root, values):
    """Record ``values`` in ``<metadata>`` and draw any that the document shows.

    Returns ``(recorded, drawn)`` - how many values were written to the record, and how many text
    elements were changed on the canvas. The two counts differ on purpose and the caller says both:
    "wrote 7 value(s), 3 shown" is the sentence that stops someone hunting for a value the drawing
    was never asked to display.
    """
    if not values:
        return 0, 0

    block = _attributes_of(root, create=True)

    existing = {}
    for element in list(block.findall(_VALUE)):
        key = element.get("key")
        if key in values:
            existing[key] = element
        elif key is None:
            block.remove(element)

    for key, value in values.items():
        text = "" if value is None else str(value)
        element = existing.get(key)
        if element is None:
            element = block.makeelement(_VALUE, {"key": key})
            block.append(element)
        element.text = text

    return len(values), draw_values(root, values)


def draw_values(root, values):
    """Put each value into the text element labelled with its key, where one exists.

    Returns how many were drawn. A key with no labelled element is skipped in silence: a drawing
    is not obliged to show every attribute of its item, and most show two or three.
    """
    drawn = 0
    for element in root.iter(_TEXT):
        key = element.get(_LABEL)
        if key is None or key not in values:
            continue
        _set_text(element, for_display(values[key]))
        drawn += 1
    return drawn


def for_display(value):
    """How a value reads on the sheet, as opposed to how it is recorded.

    The record keeps exactly what the service sent - that is the truth, and Refresh Values has to
    be able to compare it. The drawing is for a person, and a person reading a title block wants
    a date, not ``2026-09-28T02:24:15.3456789Z``, which is what the first drawn sheet showed in
    its DATE box.

    Only the obvious case is handled: an ISO timestamp becomes its date. Anything else is left
    exactly as it came, because guessing at a format is how a part number loses a character.
    """
    if value is None:
        return ""
    text = str(value)
    if len(text) >= 11 and text[10] == "T" and text[4] == "-" and text[7] == "-":
        head = text[:10]
        if head.replace("-", "").isdigit():
            return head
    return text


def _set_text(element, value):
    """Replace a ``<text>``'s content, keeping the first ``<tspan>``'s styling.

    A bare ``element.text = value`` looks right and is wrong: Inkscape writes its text inside a
    ``<tspan>`` that carries the position and style, so setting the parent's text leaves the old
    span in place underneath and the drawing shows both the new value and the old one.
    """
    spans = element.findall(_TSPAN)
    if not spans:
        element.text = value
        return

    keeper = spans[0]
    for extra in spans[1:]:
        element.remove(extra)
    # Nested tspans carry their own text; drop them so the value is not duplicated.
    for nested in list(keeper.findall(_TSPAN)):
        keeper.remove(nested)
    element.text = None
    keeper.text = value


def labelled_keys(root):
    """Every key the drawing is prepared to show, from its labelled text elements.

    Used to tell the user which attributes this drawing displays, and by the template builder to
    check a template really does what it claims.
    """
    keys = []
    for element in root.iter(_TEXT):
        key = element.get(_LABEL)
        if key and key not in keys:
            keys.append(key)
    return keys


def cloned_with_values(root, values):
    """A deep copy of the tree with ``values`` applied - for comparing without changing anything."""
    duplicate = copy.deepcopy(root)
    write_values(duplicate, values)
    return duplicate


def write_into_file(path, values):
    """Put ``values`` into an SVG **file**, for a drawing Inkscape has not opened yet.

    This is the one place the add-in writes a real path, and it is safe for the one reason that
    matters: the file is a freshly staged drawing that nothing has open. The rule against writing
    the document's path is about the file Inkscape is *showing* - there, Inkscape owns the buffer
    and would overwrite or ignore anything written underneath it.

    It exists because New from Template opens the staged file in a **new** Inkscape process, so
    there is no in-memory document to put the values into. Without this the drawing opens with the
    template's own placeholders - a title block full of "-" on an item PLM has just numbered,
    which is exactly what driving it showed. LibreOffice's add-in learnt the same lesson and
    writes into the staged file for the same reason.

    Returns ``(recorded, drawn)`` as :func:`write_values` does, or ``(0, 0)`` when there is
    nothing to write. Handles ``.svgz`` (gzipped SVG), which Inkscape writes and reads.
    """
    if not path or not values:
        return 0, 0

    from lxml import etree

    gzipped = str(path).lower().endswith(".svgz")
    opener = _gzip_open if gzipped else open

    with opener(path, "rb") as handle:
        tree = etree.parse(handle)

    root = tree.getroot()
    recorded, drawn = write_values(root, values)

    with opener(path, "wb") as handle:
        handle.write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    return recorded, drawn


def _gzip_open(path, mode):
    import gzip
    return gzip.open(path, mode)
