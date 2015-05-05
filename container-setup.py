# /container-setup.py
#
# Initial setup script specific to polysquare-travis-container. Creates
# a cache dir in the container and sets the
# _POLYSQUARE_TRAVIS_CONTAINER_TEST_CACHE_DIR environment variable
# to point to it.
#
# See /LICENCE.md for Copyright information
"""Initial setup script specific to polysquare-ci-scripts."""

import os


def run(cont, util, shell, argv=list()):
    """Set up language runtimes and pass control to python project script."""

    cache_dir = cont.named_cache_dir("travis_container_downloads")
    cache_dir_key = "_POLYSQUARE_TRAVIS_CONTAINER_TEST_CACHE_DIR"
    shell.overwrite_environment_variable(cache_dir_key, cache_dir)

    cont.fetch_and_import("setup/python/setup.py").run(cont, util, shell, argv)
