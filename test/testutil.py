# /test/testutil.py
#
# Monkey-patch functions for tests to cache downloaded files. This helps
# to speed up test execution.
#
# See /LICENCE.md for Copyright information
"""Monkey-patch functions for tests to cache downloaded files."""

import errno

import os

import shutil

import sys

from base64 import urlsafe_b64encode as b64

from psqtraviscontainer.download import download_file as download_file_original

from termcolor import colored


def download_file_cached(url, filename=None):
    """Check if we've got a cached version of url, otherwise download it."""
    cache_dir = os.environ.get("_POLYSQUARE_TRAVIS_CONTAINER_TEST_CACHE_DIR",
                               None)
    if cache_dir:
        try:
            os.makedirs(cache_dir)
        except OSError as error:
            if error.errno != errno.EEXIST:  # suppress(PYC90)
                raise error

        dest_filename = os.path.realpath(filename or os.path.basename(url))
        base64_filename = os.path.join(cache_dir, b64(url.encode()))

        if os.path.exists(base64_filename):
            sys.stdout.write(colored("""-> Downloading {0} """
                                     """[found in cache]\n""".format(url),
                                     "blue",
                                     attrs=["bold"]))
            shutil.copyfile(base64_filename, dest_filename)
        else:
            # Grab the url and then store the downloaded file in the cache.
            # We trust download_file_original to give us the
            # right dest_filename, hence the reason why we overwrite it here.
            dest_filename = download_file_original(url, filename)
            shutil.copyfile(dest_filename, base64_filename)
    else:
        dest_filename = download_file_original(url, filename)

    return dest_filename
