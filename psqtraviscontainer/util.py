# /psqtraviscontainer/util.py
#
# Utility functions for working with files.
#
# See /LICENCE.md for Copyright information
"""Utility functions for working with files."""

import os


def check_if_exists(entity):
    """Raise RuntimeError if entity does not exist."""
    if not os.path.exists(entity):
        raise RuntimeError("""A required entity {0} does not exist\n"""
                           """Try running psq-travis-container-create """
                           """first before using psq-travis-container-use."""
                           """""".format(entity))
