# /psqtraviscontainer/constants.py
#
# Constants shared across modules.
#
# See /LICENCE.md for Copyright information
"""Various constants useful for use and create modules."""

import os


def have_proot_distribution(cwd):
    """Return proot distribution stamp filename."""
    return os.path.join(cwd, ".have-proot-distribution")


def proot_distribution_dir(cwd):
    """Return proot distribution dir from cwd."""
    return os.path.join(cwd, "_proot")
