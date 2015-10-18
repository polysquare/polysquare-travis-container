# /psqtraviscontainer/download.py
#
# Module with utilities for downloading files.
#
# See /LICENCE.md for Copyright information
"""Module with utilities for downloading files."""

import os

import sys

from clint.textui import colored, progress

import requests


def download_file(url, filename=None):
    """Download the file at url and store it at filename."""
    basename = os.path.basename(filename or url)
    msg = """Downloading {dest} (from {source})""".format(source=url,
                                                          dest=basename)
    sys.stdout.write(str(colored.blue(msg, bold=True)))
    sys.stdout.write("\n")
    request = requests.get(url, stream=True)
    length = int(request.headers.get("content-length"))
    with open(filename or os.path.basename(url), "wb") as downloaded_file:
        chunk_size = 1024
        total = length / chunk_size + 1
        for chunk in progress.bar(request.iter_content(chunk_size=chunk_size),
                                  expected_size=total,
                                  label=basename):
            downloaded_file.write(chunk)
            downloaded_file.flush()

    return os.path.join(os.getcwd(), downloaded_file.name)


class TemporarilyDownloadedFile(object):  # pylint:disable=R0903
    """An enter/exit class representing a temporarily downloaded file.

    The file will be downloaded on enter and erased once the scope has
    been exited.
    """

    def __init__(self, url, filename=None):
        """Initialize the url and path to download file to."""
        super(TemporarilyDownloadedFile, self).__init__()
        self._url = url
        self._path = download_file(self._url, filename)

    def __enter__(self):
        """Run file download."""
        return self

    def __exit__(self, exc_type, value, traceback):
        """Remove the temporarily downloaded file."""
        del exc_type
        del traceback
        del value

        os.remove(self._path)
        self._path = None

    def path(self):
        """Get temporarily downloaded file path."""
        return self._path
