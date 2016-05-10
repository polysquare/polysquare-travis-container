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

    cache_dir = cont.named_cache_dir("travis_container_downloads",
                                     ephemeral=False)
    cache_dir_key = "_POLYSQUARE_TRAVIS_CONTAINER_TEST_CACHE_DIR"
    shell.overwrite_environment_variable(cache_dir_key, cache_dir)

    cont.fetch_and_import("setup/python/setup.py").run(cont, util, shell, argv)

    config_python = "setup/project/configure_python.py"
    py_ver = util.language_version("python3")
    py_cont = cont.fetch_and_import(config_python).get(cont,
                                                       util,
                                                       shell,
                                                       py_ver)

    with py_cont.activated(util):
        with util.Task("""Downloading all distributions"""):
            os.environ[cache_dir_key] = cache_dir
            util.execute(cont,
                         util.long_running_suppressed_output(),
                         util.which("python"),
                         "download-all-distros-to.py")
