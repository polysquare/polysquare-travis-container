# /test/testutil.py
#
# Monkey-patch functions for tests to cache downloaded files. This helps
# to speed up test execution.
#
# See /LICENCE.md for Copyright information
"""Monkey-patch functions for tests to cache downloaded files."""

import errno

import hashlib

import os

import shutil

import sys

from contextlib import contextmanager

from clint.textui import colored

from psqtraviscontainer.download import download_file as download_file_original


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
        hashed = os.path.join(cache_dir,
                              hashlib.md5(url.encode("utf-8")).hexdigest())

        if os.path.exists(hashed):
            msg = """Downloading {0} [found in cache]\n""".format(url)
            sys.stdout.write(str(colored.blue(msg, bold=True)))
            shutil.copyfile(hashed, dest_filename)
        else:
            # Grab the url and then store the downloaded file in the cache.
            # We trust download_file_original to give us the
            # right dest_filename, hence the reason why we overwrite it here.
            dest_filename = download_file_original(url, filename)
            shutil.copyfile(dest_filename, hashed)
    else:
        dest_filename = download_file_original(url, filename)

    return dest_filename


@contextmanager
def temporary_environment(**kwargs):
    """A context with os.environ set to a temporary value."""
    environ_copy = os.environ.copy()
    os.environ.update(kwargs)
    try:
        yield
    finally:
        os.environ = environ_copy
