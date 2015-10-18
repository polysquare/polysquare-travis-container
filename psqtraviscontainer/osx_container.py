# /psqtraviscontainer/osx_container.py
#
# Specialization for OS X containers, using environment variables.
#
# See /LICENCE.md for Copyright information
"""Specialization for OS X containers, using environment variables."""

import os

import platform

import shutil

import tarfile

from clint.textui import colored

from psqtraviscontainer import container
from psqtraviscontainer import directory
from psqtraviscontainer import distro
from psqtraviscontainer import package_system
from psqtraviscontainer import printer
from psqtraviscontainer import util

from psqtraviscontainer.download import TemporarilyDownloadedFile

import tempdir

DistroInfo = distro.DistroInfo

_HOMEBREW_URL = "https://github.com/Homebrew/homebrew/tarball/master"


class OSXContainer(container.AbstractContainer):
    """A container for OS X.

    We can execute commands inside this container by setting the
    required environment variables to pick commands from this
    path.
    """

    def __init__(self,  # suppress(too-many-arguments)
                 homebrew_distribution,
                 pkg_sys_constructor):
        """Initialize this OSXContainer, storing its distro configuration."""
        super(OSXContainer, self).__init__()
        self._prefix = homebrew_distribution
        self._pkgsys = pkg_sys_constructor(self)

    def _subprocess_popen_arguments(self, argv, **kwargs):
        """For native arguments argv, return AbstractContainer.PopenArguments.

        This returned tuple will have no environment variables set, but the
        proot command to enter this container will be prepended to the
        argv provided.
        """
        del kwargs

        popen_args = self.__class__.PopenArguments
        popen_env = {
            "PATH": os.path.join(self._prefix, "bin"),
            "LD_LIBRARY_PATH": os.path.join(self._prefix, "lib"),
            "PKG_CONFIG_PATH": os.path.join(self._prefix, "lib", "pkgconfig")
        }
        return popen_args(prepend=popen_env, argv=argv)

    def _root_filesystem_directory(self):
        """Return directory on parent filesystem where our root is located."""
        return self._prefix

    def _package_system(self):
        """Return package system for this distribution."""
        return self._pkgsys

    def clean(self):
        """Clean out this container to prepare it for caching."""
        pass


def _extract_archive(archive_file, container_folder):
    """Extract distribution archive into container_folder."""
    with tarfile.open(name=archive_file.path()) as archive:
        msg = ("""-> Extracting """
               """{0}\n""").format(archive_file.path())
        extract_members = archive.getmembers()
        printer.unicode_safe(colored.magenta(msg, bold=True))
        archive.extractall(members=extract_members, path=container_folder)


def container_for_directory(container_dir, distro_config):
    """Return an existing OSXContainer at container_dir for distro_config.

    Also take into account arguments in result to look up the the actual
    directory for this distro.
    """
    util.check_if_exists(os.path.join(container_dir, "bin", "brew"))

    return OSXContainer(container_dir, distro_config["pkgsys"])


def _fetch_homebrew(container_dir, distro_config):
    """Fetch homebrew and untar it in the container directory."""
    try:
        os.stat(os.path.join(container_dir, "bin", "brew"))
        return container_for_directory(container_dir, distro_config)
    except OSError:
        with directory.Navigation(tempdir.TempDir().name):
            with TemporarilyDownloadedFile(_HOMEBREW_URL) as archive_file:
                with directory.Navigation(tempdir.TempDir().name) as extract:
                    _extract_archive(archive_file, extract)
                    first = os.path.join(extract,
                                         os.listdir(extract)[0])
                    files = [os.path.join(first, p) for p in os.listdir(first)]
                    for filename in files:
                        try:
                            filename_base = os.path.basename(filename)
                            shutil.move(filename, os.path.join(container_dir,
                                                               filename_base))
                        except IOError:  # suppress(pointless-except)
                            # Ignore stuff that can't be moved for whatever
                            # reason. These are all files that generally
                            # don't matter.
                            pass

        return OSXContainer(container_dir, distro_config["pkgsys"])


def create(container_dir, distro_config):
    """Create a container using homebrew."""
    # First fetch a proot distribution if we don't already have one
    return _fetch_homebrew(container_dir, distro_config)


def match(info, arguments):
    """Check for matching configuration from DISTRIBUTIONS for arguments.

    In effect, this just means checking if we're on OS X.
    """
    if platform.system() != "Darwin":
        return None

    if arguments.get("distro", None) != "OSX":
        return None

    return info.kwargs


def enumerate_all(info):
    """Enumerate all valid configurations for this DistroInfo."""
    if platform.system() != "Darwin":
        return

    yield info.kwargs


DISTRIBUTIONS = [
    DistroInfo(create_func=create,
               get_func=container_for_directory,
               match_func=match,
               enumerate_func=enumerate_all,
               kwargs={
                   "distro": "OSX",
                   "pkgsys": package_system.Brew   # suppress(PYC50)
               })
]
