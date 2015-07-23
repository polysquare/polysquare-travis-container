# /psqtraviscontainer/printer.py
#
# Utility functions for printing unicode text.
#
# See /LICENCE.md for Copyright information
"""Utility functions for printing unicode text."""

import platform

import sys


def unicode_safe(text):
    """Print text to standard output, handle unicode."""
    # If a replacement of sys.stdout doesn't have isatty, don't trust it.
    # Also don't trust Windows to get this right either.
    if (not getattr(sys.stdout, "isatty", None) or
            not sys.stdout.isatty() or
            platform.system() == "Windows"):
        text = "".join([c for c in str(text) if ord(c) < 128])

    sys.stdout.write(str(text))
