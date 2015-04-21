# /psqtraviscontainer/download.py
#
# Module with utilities for downloading files.
#
# See /LICENCE.md for Copyright information
"""Module with utilities for downloading files."""

import os

import sys

from termcolor import colored

from urlgrabber.grabber import URLGrabber

from urlgrabber.progress import TextMeter


def download_file(url, filename=None):
    """Download the file at url and store it at filename."""
    sys.stdout.write(colored("-> Downloading {0}\n".format(url),
                             "blue",
                             attrs=["bold"]))
    grabber = URLGrabber(timeout=10,
                         progress_obj=TextMeter(fo=sys.stdout),
                         retry=3)
    grabbed_filename = grabber.urlgrab(str(url), filename=filename)

    return os.path.join(os.getcwd(), grabbed_filename)


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
