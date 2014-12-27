# /psqtraviscontainer/package_system.py
#
# Implementations of package-system controllers for various distributions.
#
# See LICENCE.md for Copyright information
"""Implementations of package-system controllers for various distributions."""

import os

_UBUNTU_MAIN_ARCHS = ["i386", "amd64"]
_UBUNTU_PORT_ARCHS = ["armhf", "arm64", "powerpc", "ppc64el"]
_UBUNTU_MAIN_ARCHIVE = "http://archive.ubuntu.com/ubuntu/"
_UBUNTU_PORT_ARCHIVE = "http://ports.ubuntu.com/ubuntu-ports/"

import sys

from psqtraviscontainer import directory
from psqtraviscontainer import download

from termcolor import colored


class Dpkg(object):

    """Debian Packaging System."""

    def __init__(self,
                 distro_dir,
                 config,
                 arch,
                 executor):
        """Initialize DpkgPackageSystem with DistroConfig."""
        super(Dpkg, self).__init__()
        self._distro_root = distro_dir
        self._config = config
        self._arch = arch
        self._executor = executor

    def add_repositories(self, repos):
        """Add a repository to the central packaging system."""
        _ubuntu_urls = [
            (_UBUNTU_MAIN_ARCHS, _UBUNTU_MAIN_ARCHIVE),
            (_UBUNTU_PORT_ARCHS, _UBUNTU_PORT_ARCHIVE)
        ]

        _launchpad_url = ["http://ppa.launchpad.net/"]
        _ubuntu_url = [u[1] for u in _ubuntu_urls if self._arch in u[0]]
        _debian_url = ["http://ftp.debian.org/"]

        def _format_user_line(line, kwargs):
            """Format a line and turns it into a valid repo line."""
            formatted_line = line.format(**kwargs)  # pylint:disable=W0142
            return "deb {0}\n".format(formatted_line)

        def _value_or_error(value):
            """Return first item in value, or ERROR if value is empty."""
            return value[0] if len(value) else "ERROR"

        # Find /etc/apt/sources.list and add the line there
        with open(os.path.join(self._distro_root, "etc/apt/sources.list"),
                  "a+") as sources:
            format_keys = {
                "ubuntu": _ubuntu_url,
                "debian": _debian_url,
                "launchpad": _launchpad_url,
                "release": [self._config.release]
            }
            format_keys = {
                k: _value_or_error(v) for k, v in format_keys.items()
            }

            sources_lines = sources.readlines()
            append_lines = [_format_user_line(l, format_keys) for l in repos]

            for append_line in append_lines:
                if append_line not in sources_lines:
                    sources.write(append_line)

    def run_task(self, description, argv):
        """Run command argv and prints description."""
        sys.stdout.write(colored("-> {0}\n".format(description), "white"))
        self._executor.execute_success(argv)

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        self.run_task("Update repositories",
                      ["apt-get", "update", "-qq", "-y"])
        self.run_task("Install {0}".format(str(package_names)),
                      ["apt-get", "install", "-qq", "-y"] + package_names)


class Yum(object):

    """RedHat Packaging System."""

    def __init__(self,
                 distro_dir,
                 config,
                 arch,
                 executor):
        """Initialize DpkgPackageSystem with DistroConfig."""
        super(Yum, self).__init__()
        self._distro_root = distro_dir
        self._config = config
        self._executor = executor

        del arch

    def add_repositories(self, repos):
        """Add a repository to the central packaging system."""
        with directory.Navigation(os.path.join(self._distro_root,
                                               "etc/yum/repos.d")):
            for repo in repos:
                download.download_file(repo)

    def run_task(self, description, argv):
        """Run command argv and prints description."""
        sys.stdout.write(colored("-> {0}\n".format(description), "white"))
        self._executor.execute_success(argv)

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        self.run_task("Install {0}".format(str(package_names)),
                      ["yum", "install", "-y"] + package_names)
