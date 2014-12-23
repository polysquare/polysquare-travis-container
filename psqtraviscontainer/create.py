# /psqtraviscontainer/create.py
#
# Module which handles the creation of proot in which APT packages
# can be readily installed
#
# See LICENCE.md for Copyright information
""" Module which handles the creation of proot.

The proot for a distribution is a special directory entered with the proot
command, which behaves like a chroot, except that no root access is required
in order to create the jail. Commands running in the proot will have filesystem
requests redirected to the proot and believe that they are running as uid 0
"""

import argparse

import errno

import os

import platform

import shutil

import sys

from collections import namedtuple

from pyunpack import Archive

from termcolor import colored

from urlgrabber.grabber import URLGrabError
from urlgrabber.grabber import URLGrabber

from urlgrabber.progress import TextMeter


DistroConfig = namedtuple("DistroConfig", "name url archs pkgsys archfetch")
ProotDistribution = namedtuple("ProotDistribution", "proot qemu")


_HAVE_PROOT_DISTRIBUTION_NAME = ".have-proot-distribution"
_PROOT_DISTRIBUTION_DIR = "_proot"
_PROOT_URL_BASE = "http://static.proot.me/proot-{arch}"
_QEMU_URL_BASE = "http://download.opensuse.org/repositories/home:/cedric-vincent/xUbuntu_12.04/{arch}/qemu-user-mode_1.6.1-1_{arch}.deb"  # NOQA # pylint:disable=line-too-long


class _DirectoryNavigation(object):

    """ContextManager based class to enter and exit directories."""

    def __init__(self, path):
        """Initialize the path we want to change to."""
        super(_DirectoryNavigation, self).__init__()
        self._path = path
        self._current_dir = None

    def __enter__(self):
        """Upon entry, attempt to create the directory and then enter it."""
        try:
            os.makedirs(self._path)
        except OSError, err:
            if err.errno != errno.EEXIST:
                raise err

        self._current_dir = os.getcwd()
        os.chdir(self._path)

        return self._path

    def __exit__(self, exc_type, value, traceback):
        """Pop directory on exiting with statement."""
        del exc_type
        del traceback
        del value

        os.chdir(self._current_dir)


_ArchitectureType = namedtuple("_ArchitectureType",
                               "aliases debian universal qemu")

_X86_ARCHITECTURE = _ArchitectureType(aliases=["i386",
                                               "i486",
                                               "i586",
                                               "i686",
                                               "x86"],
                                      debian="i386",
                                      universal="x86",
                                      qemu="i386")
_X86_64_ARCHITECTURE = _ArchitectureType(aliases=["x86_64", "amd64"],
                                         debian="amd64",
                                         universal="x86_64",
                                         qemu="x86_64")
_ARM_HARD_FLOAT_ARCHITECTURE = _ArchitectureType(aliases=["arm",
                                                          "armel",
                                                          "armhf"],
                                                 debian="amd64",
                                                 universal="x86_64",
                                                 qemu="x86_64")


class _ArchitectureAliasMetaclass(type):

    """A metaclass which provides an operator to convert arch strings."""

    @classmethod
    def __getitem__(cls,  # pylint:disable=bad-mcs-classmethod-argument
                    lookup):
        """Operator overload for [].

        If a special architecture for different platforms is not found, return
        a generic one which just has this architecture name
        """
        del cls

        overloaded_architectures = [_X86_ARCHITECTURE,
                                    _X86_64_ARCHITECTURE,
                                    _ARM_HARD_FLOAT_ARCHITECTURE]
        for arch in overloaded_architectures:
            if lookup in arch.aliases:
                return arch

        return _ArchitectureType(aliases=[lookup],
                                 debian=lookup,
                                 universal=lookup,
                                 qemu=lookup)


class _ArchitectureAlias(object):

    """Implementation of _ArchitectureAliasMetaclass.

    Provides convenience methods to convert architecture strings
    between platforms.
    """

    __metaclass__ = _ArchitectureAliasMetaclass

    @classmethod
    def debian(cls, lookup):
        """Convert to debian."""
        return cls[lookup].debian

    @classmethod
    def qemu(cls, lookup):
        """Convert to qemu."""
        return cls[lookup].qemu

    @classmethod
    def universal(cls, lookup):
        """Convert to universal."""
        return cls[lookup].universal


def _download_file(url, filename):
    """Download the file at url and store it at filename."""
    try:

        sys.stdout.write(colored("Downloading {0} to {1}".format(url,
                                                                 filename),
                                 "blue",
                                 attrs=["bold"]))
        grabber = URLGrabber(timeout=10,
                             progress_obj=TextMeter(fo=sys.stdout))
        grabber.urlgrab(url, filename=filename)

    except URLGrabError, exc:
        sys.stdout.write(str(exc))


class _TemporarilyDownloadedFile(object):\

    """An enter/exit class representing a temporarily downloaded file.

    The file will be downloaded on enter and erased once the scope has
    been exited.
    """

    def __init__(self, url, filename):
        """Initialize the url and path to download file to."""
        super(_TemporarilyDownloadedFile, self).__init__()
        self._url = url
        self._path = os.path.join(os.getcwd(), filename)

    def __enter__(self):
        """Run file download."""
        _download_file(self._url, self._path)
        return self

    def __exit__(self, exc_type, value, traceback):
        """Remove the temporarily downloaded file."""
        del exc_type
        del traceback
        del value

        os.remove(self._path)

    def path(self):
        """Get temporarily downloaded file path."""
        return self._path


def _fetch_proot_distribution(container_root):
    """Fetch the initial proot distribution if it is not available.

    Touches .have-proot-distribution when complete
    """
    path_to_proot_distro_check = os.path.join(container_root,
                                              _HAVE_PROOT_DISTRIBUTION_NAME)
    path_to_proot_dir = os.path.join(container_root,
                                     _PROOT_DISTRIBUTION_DIR)

    try:
        os.stat(path_to_proot_distro_check)
        sys.stdout.write(colored("Using pre-existing proot distribution",
                                 "green",
                                 attrs=["bold"]))
    except OSError:

        sys.stdout.write(colored(("Creating distribution of proot "
                                  "in {0}").format(container_root),
                                 "yellow",
                                 attrs=["bold"]))

        # Distro check does not exist - create the _proot directory
        # and download files for this architecture
        with _DirectoryNavigation(path_to_proot_dir):
            proot_arch = _ArchitectureAlias.universal(platform.machine())
            qemu_arch = _ArchitectureAlias.debian(platform.machine())

            with _DirectoryNavigation(os.path.join(path_to_proot_dir,
                                                   "bin")):
                proot_url = _PROOT_URL_BASE.format(arch=proot_arch)
                _download_file(proot_url, "proot")

            qemu_url = _QEMU_URL_BASE.format(arch=qemu_arch)

            with _TemporarilyDownloadedFile(qemu_url,
                                            filename="qemu.deb") as qemu_deb:

                # Go into a separate subdirectory and extract the qemu deb
                # there, then copy out the requisite files, so that we don't
                # cause tons of pollution
                qemu_tmp = os.path.join(path_to_proot_dir, "_qemu_tmp")
                with _DirectoryNavigation(qemu_tmp):
                    sys.stdout.write(colored(("Extracting "
                                              "{0}").format(qemu_deb.path()),
                                             "magenta",
                                             attrs=["bold"]))
                    archive = Archive(qemu_deb.path())
                    archive.extractall(qemu_tmp)

                    qemu_binaries_path = os.path.join(qemu_tmp, "usr/bin")
                    for filename in os.listdir(qemu_binaries_path):
                        shutil.copy(os.path.join(qemu_binaries_path, filename),
                                    os.path.join(path_to_proot_dir, "bin"))

                shutil.rmtree(qemu_tmp)

        with open(path_to_proot_distro_check, "w+") as check_file:
            check_file.write("done")

        sys.stdout.write(colored(("Successfully installed proot distribution"
                                  " to {0}").format(container_root),
                                 "green",
                                 attrs=["bold"]))

    def _get_qemu_binary(arch):
        """Get the qemu binary for architecture."""
        path_to_qemu = os.path.join(path_to_proot_dir, "bin/qemu-{arch}")
        return path_to_qemu.format(_ArchitectureAlias.qemu(arch))

    def _get_proot_binary():
        """Get the proot binary."""
        return os.path.join(path_to_proot_dir, "bin/proot")

    return ProotDistribution(proot=_get_proot_binary,
                             qemu=_get_qemu_binary)


class DpkgPackageSystem(object):

    """Debian Packaging System."""

    pass

AVAILABLE_DISTRIBUTIONS = [
    DistroConfig(name="ubuntu-precise",
                 url="http://cdimage.ubuntu.com/ubuntu-core/releases/precise/release/ubuntu-core-12.04.5-core-{arch}.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["i386", "amd64", "armhf"],
                 pkgsys=DpkgPackageSystem,
                 archfetch=_ArchitectureAlias.debian),
    DistroConfig(name="ubuntu-trusty",
                 url="http://cdimage.ubuntu.com/ubuntu-core/releases/precise/release/ubuntu-core-14.04.1-core-{arch}.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["i386",
                        "amd64",
                        "armhf",
                        "arm64",
                        "powerpc",
                        "ppc64el"],
                 pkgsys=DpkgPackageSystem,
                 archfetch=_ArchitectureAlias.debian)
]


def _parse_arguments(arguments=None):
    """Return a parser context result."""
    # Iterate over the AVAILABLE_DISTRIBUTIONS and get a list of available
    # distributions and architecutres for the --distro and --arch arguments
    available_architectures = set()
    available_distributions = set()

    for distro in AVAILABLE_DISTRIBUTIONS:
        available_distributions.add(distro.name)

        for arch in distro.archs:
            available_architectures.add(_ArchitectureAlias.universal(arch))

    parser = argparse.ArgumentParser(description="Create a Travis container")

    parser.add_argument("containerdir",
                        nargs=1,
                        metavar=("CONTAINER_DIRECTORY"),
                        help="Directory to place container in",
                        type=str)
    parser.add_argument("--distro",
                        nargs=1,
                        type=str,
                        help="Distribution name to create container of",
                        default=None,
                        choices=available_distributions)
    parser.add_argument("--arch",
                        nargs=1,
                        type=str,
                        help=("Architecture (all architectures other than "
                              "the system architecture will be emulated with "
                              "qemu)"),
                        default=platform.machine(),
                        choices=available_architectures)

    return parser.parse_args(arguments)


def _print_distribution_details(details, selected_arch):
    """Print distribution details."""
    distro_arch = details.archfetch(selected_arch)
    pkgsysname = details.pkgsys.__name__

    sys.stdout.write(colored("\nConfigured Distribution:\n",
                             "white",
                             attrs=["underline"]) +
                     " - Distribution Name: {0}\n".format(colored(details.name,
                                                                  "yellow")) +
                     " - Architecture: {0}\n".format(colored(distro_arch,
                                                             "yellow")) +
                     " - Package System: {0}\n".format(colored(pkgsysname,
                                                               "yellow")))


def main(arguments=None):
    """Parse arguments and set up proot.

    Parse arguments, fetches initial proot distribution and downloads
    and sets up our proot.
    """
    result = _parse_arguments(arguments=arguments)

    # First fetch a proot distribution if we don't already have one
    _fetch_proot_distribution(result.containerdir[0])

    # Now fetch the distribution tarball itself, if we specified one
    if result.distro:
        available = AVAILABLE_DISTRIBUTIONS
        details = [d for d in available if d.name == result.distro[0]]

        _print_distribution_details(details[0], result.arch)

    sys.stdout.write(colored("Container has been set up "
                             "in {0}".format(result.containerdir[0]),
                             "green",
                             attrs=["bold"]))

if __name__ == "__main__":
    main()
