# /psqtraviscontainer/package_system.py
#
# Implementations of package-system controllers for various distributions.
#
# See /LICENCE.md for Copyright information
"""Implementations of package-system controllers for various distributions."""

import abc

import fnmatch

import os

import sys

import tempfile

from collections import namedtuple

from clint.textui import colored

from psqtraviscontainer import debian
from psqtraviscontainer import directory
from psqtraviscontainer import download

import six

import tempdir

_UBUNTU_MAIN_ARCHS = ["i386", "amd64"]
_UBUNTU_PORT_ARCHS = ["armhf", "arm64", "powerpc", "ppc64el"]
_UBUNTU_MAIN_ARCHIVE = "http://archive.ubuntu.com/ubuntu/"
_UBUNTU_PORT_ARCHIVE = "http://ports.ubuntu.com/ubuntu-ports/"


def _report_task(description):
    """Report task description."""
    sys.stdout.write(str(colored.white("-> {0}\n".format(description))))


def _run_task(executor, description, argv):
    """Run command through executor argv and prints description."""
    _report_task(description)
    executor.execute(argv, requires_full_access=True)


class PackageSystem(six.with_metaclass(abc.ABCMeta, object)):
    """An abstract class representing a package manager."""

    PopenArguments = namedtuple("PopenArguments", "argv env")

    @abc.abstractmethod
    def add_repositories(self, repos):
        """Add repositories to central packaging system."""
        del repos

        raise NotImplementedError()

    @abc.abstractmethod
    def install_packages(self, package_names):
        """Install specified packages in package_names."""
        del package_names

        raise NotImplementedError()


class Dpkg(PackageSystem):
    """Debian Packaging System."""

    def __init__(self,
                 release,
                 arch,
                 executor):
        """Initialize Dpkg with release and arch."""
        super(Dpkg, self).__init__()
        self._release = release
        self._arch = arch
        self._executor = executor

    def add_repositories(self, repos):
        """Add a repository to the central packaging system."""
        _ubuntu_urls = [
            (_UBUNTU_MAIN_ARCHS, _UBUNTU_MAIN_ARCHIVE),
            (_UBUNTU_PORT_ARCHS, _UBUNTU_PORT_ARCHIVE)
        ]

        def _format_user_line(line, kwargs):
            """Format a line and turns it into a valid repo line."""
            formatted_line = line.format(**kwargs)
            return "deb {0}".format(formatted_line)

        def _value_or_error(value):
            """Return first item in value, or ERROR if value is empty."""
            return value[0] if len(value) else "ERROR"

        format_keys = {
            "ubuntu": [u[1] for u in _ubuntu_urls if self._arch in u[0]],
            "debian": ["http://ftp.debian.org/"],
            "launchpad": ["http://ppa.launchpad.net/"],
            "release": [self._release]
        }
        format_keys = {
            k: _value_or_error(v) for k, v in format_keys.items()
        }

        # We will be creating a bash script each time we need to add
        # a new source line to our sources list and executing that inside
        # the proot. This guarantees that we'll always get the right
        # permissions.
        with tempfile.NamedTemporaryFile() as bash_script:
            append_lines = [_format_user_line(l, format_keys) for l in repos]
            for count, append_line in enumerate(append_lines):
                path = "/etc/apt/sources.list.d/{0}.list".format(count)
                append_cmd = "echo \"{0}\" > {1}\n".format(append_line, path)
                bash_script.write(six.b(append_cmd))

            bash_script.flush()
            self._executor.execute_success(["bash", bash_script.name],
                                           requires_full_access=True)

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        _run_task(self._executor,
                  """Update repositories""",
                  ["apt-get", "update", "-qq", "-y", "--force-yes"])
        _run_task(self._executor,
                  """Install {0}""".format(str(package_names)),
                  ["apt-get",
                   "install",
                   "-qq",
                   "-y",
                   "--force-yes"] + package_names)


class DpkgLocal(PackageSystem):
    """Debian packaging system, installing packages to local directory."""

    def __init__(self, release, arch, executor):
        """Initialize this DpkgLocal PackageSystem."""
        self._dpkg_system = Dpkg(release, arch, executor)
        self._executor = executor

    def add_repositories(self, repos):
        """Add repository to the central packaging system."""
        return self._dpkg_system.add_repositories(repos)

    def install_packages(self, package_names):
        """Install all packages in list package_names.

        This works in a somewhat non-standard way. We will be
        updating the repository list as usual, but will be
        using a combination of apt-get download and
        dpkg manually to install packages into a local
        directory which we control.
        """
        _run_task(self._executor,
                  """Update repositories""",
                  ["apt-get", "update", "-qq", "-y", "--force-yes"])
        with tempdir.TempDir() as download_dir:
            with directory.Navigation(download_dir):
                root = self._executor.root_filesystem_directory()
                _run_task(self._executor,
                          """Downloading {}""".format(package_names),
                          ["apt-get", "download"] + package_names)
                debs = fnmatch.filter(os.listdir("."), "*.deb")
                for deb in debs:
                    _report_task("""Extracting {}""".format(deb))
                    debian.extract_deb_data(deb, root)


class Yum(PackageSystem):
    """Red Hat Packaging System."""

    def __init__(self,
                 release,
                 arch,
                 executor):
        """Initialize Yum with release and executor."""
        del arch
        del release

        super(Yum, self).__init__()
        self._executor = executor

    def add_repositories(self, repos):
        """Add a repository to the central packaging system."""
        with tempdir.TempDir() as download_dir:
            with directory.Navigation(download_dir):
                for repo in repos:
                    repo_file = download.download_file(repo)
                    # Create a bash script to copy the downloaded repo file
                    # over to /etc/yum/repos.d
                    with tempfile.NamedTemporaryFile() as bash_script:
                        copy_cmd = ("cp \"{0}\""
                                    "/etc/yum/repos.d").format(repo_file)
                        bash_script.write(six.b(copy_cmd))
                        bash_script.flush()
                        self._executor.execute_success(["bash",
                                                        bash_script.name])

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        _run_task(self._executor,
                  """Install {0}""".format(str(package_names)),
                  ["yum", "install", "-y"] + package_names)


class Brew(PackageSystem):
    """Homebrew packaging system for OS X."""

    def __init__(self, executor):
        """Initialize homebrew for executor."""
        super(Brew, self).__init__()
        self._executor = executor

    def add_repositories(self, repos):
        """Add repositories as specified at repos.

        Adds repositories using brew tap.
        """
        for repo in repos:
            _run_task(self._executor,
                      """Adding repository {0}""".format(repo),
                      ["brew", "tap", repo])

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        _run_task(self._executor,
                  """Install {0}""".format(str(package_names)),
                  ["brew", "install"] + package_names)


class Choco(PackageSystem):
    """Chocolatey packaging system for Windows."""

    def __init__(self, executor):
        """Initialize choco for executor."""
        super(Choco, self).__init__()
        self._executor = executor

    def add_repositories(self, repos):
        """Add repositories as specified at repos.

        This function doesn't do anything on Choco at the moment.
        """
        pass

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        _run_task(self._executor,
                  """Install {0}""".format(str(package_names)),
                  ["choco", "install", "-fy", "-m"] + package_names)
