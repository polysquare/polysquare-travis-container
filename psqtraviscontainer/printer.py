# /psqtraviscontainer/printer.py
#
# Utility functions for printing unicode text.
#
# See /LICENCE.md for Copyright information
"""Utility functions for printing unicode text."""

import sys


def unicode_safe(text):
    """Print text to standard output, handle unicode."""
    # If a replacement of sys.stdout doesn't have isatty, don't trust it.
    if not getattr(sys.stdout, "isatty", None) or not sys.stdout.isatty():
        text = "".join([c for c in text if ord(c) < 128])

    sys.stdout.write(text)
