#!/usr/bin/env python3
"""The one script behind every Nexus PLM entry in Inkscape's Extensions menu.

Each ``.inx`` names the same script and passes a different ``--command``. One script rather than
twenty means the dispatch table, the error handling and the "tray is not running" message exist
once; twenty near-identical files is how one of them quietly stops matching the others.

Inkscape shows an extension's **stderr in a dialog**, which is the only way an add-in here can put
a sentence in front of someone when the thing that draws toasts is itself not running. That is
what :func:`inkex.errormsg` writes to, and it is why the unreachable-service case is handled here
rather than left to the command.
"""

import os
import sys
import warnings

# Inkscape shows whatever an extension writes to stderr in a DIALOG. That is a feature - it is how
# the "tray is not running" message reaches someone - but it means stderr is a USER INTERFACE, not
# a developer channel. A Python warning there is an error popup in front of someone whose command
# worked, which is exactly what a stray ResourceWarning about a spawned Inkscape produced.
#
# Warnings are for whoever is writing this file, and they can run the tests. Nobody using Inkscape
# should be shown one.
warnings.simplefilter("ignore")

# The package sits beside this file. Inkscape puts the .inx's own directory on sys.path, but says
# nothing about doing so for a subdirectory, and an extension that only works because of an
# undocumented convenience is one that breaks on the next release.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import inkex                                                        # noqa: E402

from nexusplm import commands                                       # noqa: E402
from nexusplm import host                                           # noqa: E402
from nexusplm.client import DEFAULT_BASE_URL, ServiceUnavailable    # noqa: E402

TRAY_IS_DOWN = (
    "Cannot reach Nexus PLM on %s\n\n"
    "Nothing can be saved to or read from PLM until the Nexus PLM tray application is running. "
    "Start it from the Start menu and run the command again." % DEFAULT_BASE_URL
)


class NexusPlm(inkex.EffectExtension):
    """Runs one Nexus PLM command against the open drawing."""

    def add_arguments(self, pars):
        pars.add_argument("--command", default="connection-status",
                          help="which Nexus PLM command this menu entry runs")

    def effect(self):
        try:
            commands.run(self.options.command, self)
        except ServiceUnavailable:
            host.log("%s: the tray application is not running" % self.options.command)
            inkex.errormsg(TRAY_IS_DOWN)


if __name__ == "__main__":
    NexusPlm().run()
