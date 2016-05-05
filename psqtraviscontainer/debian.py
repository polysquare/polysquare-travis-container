# /psqtraviscontainer/debian.py
#
# Functionality common to debian packages.
#
# See /LICENCE.md for Copyright information
"""Functionality common to debian packages."""

import tarfile

from contextlib import closing


def extract_deb_data(archive, extract_dir):
    """Extract archive to extract_dir."""
    # We may not have python-debian installed on all platforms
    from debian import arfile  # suppress(import-error)

    with closing(arfile.ArFile(archive).getmember("data.tar.gz")) as member:
        with tarfile.open(fileobj=member,
                          mode="r|*") as data_tar:
            data_tar.extractall(path=extract_dir)
