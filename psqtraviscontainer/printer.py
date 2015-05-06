# /psqtraviscontainer/printer.py
#
# Utility functions for printing unicode text.
#
# See /LICENCE.md for Copyright information
"""Utility functions for printing unicode text."""

import sys


def unicode_safe(text):
    """Print text to standard output, handle unicode."""
    # Don't trust non-file like replacements of sys.stdout, assume
    # that they can only handle ascii.
    if sys.stdout.__class__ is not file or not sys.stdout.isatty():
        text = "".join([c for c in text if ord(c) < 128])

    sys.stdout.write(text)
