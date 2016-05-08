# /psqtraviscontainer/windows_container.py
#
# Specialization for Windows containers, using environment variables.
#
# See /LICENCE.md for Copyright information
"""Specialization for Windows containers, using environment variables."""

import errno

import fnmatch

import os

import platform

import subprocess

import sys

from psqtraviscontainer import container
from psqtraviscontainer import directory
from psqtraviscontainer import distro
from psqtraviscontainer import package_system
from psqtraviscontainer import util

import tempdir

DistroInfo = distro.DistroInfo

_CHOCO_URL = "https://chocolatey.org/install.ps1"
_CHOCO_INSTALL_CMD = ("iex ((new-object net.webclient).DownloadString('" +
                      _CHOCO_URL + "'))")


class WindowsContainer(container.AbstractContainer):
    """A container for Windows.

    We can execute commands inside this container by setting the
    required environment variables to pick commands from this
    path.
    """

    def __init__(self,  # suppress(too-many-arguments)
                 chocolatey_distribution,
                 pkg_sys_constructor):
        """Initialize this WindowsContainer, storing its distro config."""
        super(WindowsContainer, self).__init__()
        self._prefix = chocolatey_distribution
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
            "PATH": os.path.join(self._prefix, "bin")
        }
        return popen_args(prepend=popen_env, argv=argv)

    def _root_filesystem_directory(self):
        """Return directory on parent filesystem where our root is located."""
        return self._prefix

    def _package_system(self):
        """Return package system for this distribution."""
        return self._pkgsys

    def clean(self):
        """Remove unnecessary files in this container."""
        rmtree = container.AbstractContainer.rmtree
        rmtree(os.path.join(self._prefix, "logs"))

        for root, directories, files in os.walk(os.path.join(self._prefix,
                                                             "lib")):
            for directory_name in directories:
                path_to_directory = os.path.join(root, directory_name)
                blacklist = [
                    "*/doc",
                    "*/man",
                    "*/html"
                ]

                for blacklisted_dir in blacklist:
                    if fnmatch.fnmatch(path_to_directory,
                                       blacklisted_dir):
                        rmtree(path_to_directory)

            for filename in files:
                path_to_file = os.path.join(root, filename)
                blacklist = [
                    "*.old"
                ]

                for blacklisted_file in blacklist:
                    if fnmatch.fnmatch(path_to_file,
                                       blacklisted_file):
                        os.remove(blacklisted_file)


def container_for_directory(container_dir, distro_config):
    """Return an existing WindowsContainer at container_dir for distro_config.

    Also take into account arguments in result to look up the the actual
    directory for this distro.
    """
    util.check_if_exists(os.path.join(container_dir, "bin", "choco.exe"))

    return WindowsContainer(container_dir, distro_config["pkgsys"])


def _execute_no_output(command):
    """Execute command, but don't show output unless it fails."""
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        raise RuntimeError("""Process {0} failed """
                           """with {1}""".format(" ".join(command),
                                                 process.returncode))


def _fetch_choco(container_dir, distro_config):
    """Fetch chocolatey and install it in the container directory."""
    try:
        os.stat(os.path.join(container_dir, "bin", "choco.exe"))
        return container_for_directory(container_dir, distro_config)
    except OSError:
        with tempdir.TempDir() as download_dir:
            with directory.Navigation(download_dir):
                _execute_no_output(["setx",
                                    "ChocolateyInstall",
                                    container_dir])

                # Also set the variable in the local environment
                # too, so that it gets propagated down to our
                # children
                os.environ["ChocolateyInstall"] = container_dir

                try:
                    os.makedirs(container_dir)
                except OSError as error:
                    if error.errno != errno.EEXIST:
                        raise error

                _execute_no_output(["powershell",
                                    "-NoProfile",
                                    "-ExecutionPolicy",
                                    "Bypass",
                                    "-Command",
                                    _CHOCO_INSTALL_CMD])

                # Reset variable back to original state to prevent
                # polluting the user's registry
                _execute_no_output(["setx",
                                    "ChocolateyInstall",
                                    ""])

        return WindowsContainer(container_dir, distro_config["pkgsys"])


def create(container_dir, distro_config):
    """Create a container using chocolatey."""
    return _fetch_choco(container_dir, distro_config)


def match(info, arguments):
    """Check for matching configuration from DISTRIBUTIONS for arguments.

    In effect, this just means checking if we're on Windows.
    """
    if platform.system() != "Windows":
        return None

    if arguments.get("distro", None) != "Windows":
        return None

    return info.kwargs


def enumerate_all(info):
    """Enumerate all valid configurations for this DistroInfo."""
    if platform.system() != "Windows":
        return

    yield info.kwargs


DISTRIBUTIONS = [
    DistroInfo(create_func=create,
               get_func=container_for_directory,
               match_func=match,
               enumerate_func=enumerate_all,
               kwargs={
                   "distro": "Windows",
                   "pkgsys": package_system.Choco
               })
]
