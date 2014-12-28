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

import os

import platform

import re

import shutil

import stat

import sys

import tarfile

from contextlib import closing

import configargparse

from debian import arfile

from psqtraviscontainer import architecture
from psqtraviscontainer import common_options
from psqtraviscontainer import constants
from psqtraviscontainer import directory
from psqtraviscontainer import distro
from psqtraviscontainer import use

from psqtraviscontainer.download import TemporarilyDownloadedFile
from psqtraviscontainer.download import download_file

from termcolor import colored

_PROOT_URL_BASE = "http://static.proot.me/proot-{arch}"
_QEMU_URL_BASE = "http://download.opensuse.org/repositories/home:/cedric-vincent/xUbuntu_12.04/{arch}/qemu-user-mode_1.6.1-1_{arch}.deb"  # NOQA # pylint:disable=line-too-long


def _fetch_proot_distribution(container_root):
    """Fetch the initial proot distribution if it is not available.

    Touches .have-proot-distribution when complete
    """
    path_to_proot_check = os.path.join(container_root,
                                       constants.HAVE_PROOT_DISTRIBUTION)
    path_to_proot_dir = os.path.join(container_root,
                                     constants.PROOT_DISTRIBUTION_DIR)

    def _download_proot(distribution_dir, arch):
        """Download arch build of proot into distribution."""
        with directory.Navigation(os.path.join(distribution_dir,
                                               "bin")):
            proot_url = _PROOT_URL_BASE.format(arch=arch)
            path_to_proot = download_file(proot_url, "proot")
            os.chmod(path_to_proot,
                     os.stat(path_to_proot).st_mode | stat.S_IXUSR)
            return path_to_proot

    def _download_qemu(distribution_dir, arch):
        """Download arch build of qemu and extract binaries."""
        qemu_url = _QEMU_URL_BASE.format(arch=arch)

        with TemporarilyDownloadedFile(qemu_url,
                                       filename="qemu.deb") as qemu_deb:
            # Go into a separate subdirectory and extract the qemu deb
            # there, then copy out the requisite files, so that we don't
            # cause tons of pollution
            qemu_tmp = os.path.join(path_to_proot_dir, "_qemu_tmp")
            with directory.Navigation(qemu_tmp):
                sys.stdout.write(colored(("-> Extracting "
                                          "{0}\n").format(qemu_deb.path()),
                                         "magenta",
                                         attrs=["bold"]))
                archive = arfile.ArFile(qemu_deb.path())
                with closing(archive.getmember("data.tar.gz")) as member:
                    with tarfile.open(fileobj=member) as data_tar:
                        data_tar.extractall(qemu_tmp)

                qemu_binaries_path = os.path.join(qemu_tmp, "usr/bin")
                for filename in os.listdir(qemu_binaries_path):
                    shutil.copy(os.path.join(qemu_binaries_path, filename),
                                os.path.join(path_to_proot_dir, "bin"))

            shutil.rmtree(qemu_tmp)
            return os.path.join(distribution_dir, "bin", "qemu-{arch}")

    try:
        os.stat(path_to_proot_check)
        sys.stdout.write(colored(u"\N{check mark} "
                                 "Using pre-existing proot distribution\n",
                                 "green",
                                 attrs=["bold"]))

    except OSError:

        sys.stdout.write(colored(("Creating distribution of proot "
                                  "in {0}\n").format(container_root),
                                 "yellow",
                                 attrs=["bold"]))

        # Distro check does not exist - create the _proot directory
        # and download files for this architecture
        with directory.Navigation(path_to_proot_dir):
            proot_arch = architecture.Alias.universal(platform.machine())
            qemu_arch = architecture.Alias.debian(platform.machine())
            _download_proot(path_to_proot_dir, proot_arch)
            _download_qemu(path_to_proot_dir, qemu_arch)

        with open(path_to_proot_check, "w+") as check_file:
            check_file.write("done")

        sys.stdout.write(colored(u"\N{check mark} "
                                 "Successfully installed proot distribution"
                                 " to {0}\n".format(container_root),
                                 "green",
                                 attrs=["bold"]))

    return use.proot_distro_from_container(container_root)


def _print_distribution_details(details, distro_arch):
    """Print distribution details."""
    pkgsysname = details.pkgsys.__name__

    sys.stdout.write(colored("\nConfigured Distribution:\n",
                             "white",
                             attrs=["underline"]) +
                     " - Distribution Name: {0}\n".format(colored(details.type,
                                                                  "yellow")) +
                     " - Release: {0}\n".format(colored(details.release,
                                                        "yellow")) +
                     " - Architecture: {0}\n".format(colored(distro_arch,
                                                             "yellow")) +
                     " - Package System: {0}\n".format(colored(pkgsysname,
                                                               "yellow")) +
                     "\n")


def _fetch_distribution(container_root,  # pylint:disable=R0913
                        proot_distro,
                        details,
                        distro_arch,
                        repositories_file,
                        packages_file):
    """Lazy-initialize distribution and return it."""
    path_to_distro_folder = distro.get_dir(container_root,
                                           details,
                                           distro_arch)

    def _download_distro(details, path_to_distro_folder):
        """Download distribution and untar it in container root."""
        download_url = details.url.format(arch=distro_arch)
        with TemporarilyDownloadedFile(download_url) as distro_archive_file:
            with directory.Navigation(path_to_distro_folder):
                with tarfile.open(distro_archive_file.path(),
                                  "r|*") as archive:
                    extract_members = [m for m in archive.getmembers()
                                       if not m.isdev()]
                with tarfile.open(distro_archive_file.path(),
                                  "r|*") as archive:
                    msg = ("-> Extracting "
                           "{0}\n").format(distro_archive_file.path())
                    sys.stdout.write(colored(msg, "magenta", attrs=["bold"]))
                    archive.extractall(members=extract_members)

    def _install_packages(details, path_to_distro_folder):
        """Install packages into the distribution."""
        if packages_file:
            proot_executor = use.PtraceRootExecutor(proot_distro,
                                                    container_root,
                                                    details,
                                                    distro_arch)
            package_system = details.pkgsys(path_to_distro_folder,
                                            details,
                                            distro_arch,
                                            proot_executor)

            # Add any repositories to the package system now
            if repositories_file:
                repo_lines = repositories_file[0].read().splitlines(False)
                package_system.add_repositories(repo_lines)

            packages = re.findall(r"\w+", packages_file[0].read())
            package_system.install_packages(packages)

    try:
        os.stat(path_to_distro_folder)
        sys.stdout.write(colored(u"\N{check mark} "
                                 "Using pre-existing folder for distro "
                                 "{0} {1} ({2})\n".format(details.type,
                                                          details.release,
                                                          distro_arch),
                                 "green",
                                 attrs=["bold"]))
    except OSError:
        # Download the distribution tarball in the distro dir
        _download_distro(details, path_to_distro_folder)

        # Now set up packages in the distribution. If more packages need
        # to be installed or the installed packages need to be updated then
        # the build cache should be cleared.
        _install_packages(details, path_to_distro_folder)

    return path_to_distro_folder


def _parse_arguments(arguments=None):
    """Return a parser context result."""
    parser = common_options.get_parser("Create")
    parser.add_argument("--repositories",
                        nargs=1,
                        type=configargparse.FileType("r"),
                        help="A file containing a list of repositories to add "
                             "before installing packages. Special keywords "
                             "will control the operation of this file: \n"
                             "{release}: The distribution release (eg, "
                             "precise)\n"
                             "{ubuntu}: Ubuntu archive URL\n"
                             "{launchpad}: Launchpad PPA URL header (eg,"
                             "ppa.launchpad.net)\n",
                        default=None)
    parser.add_argument("--packages",
                        nargs=1,
                        type=configargparse.FileType("r"),
                        help="A file containing a list of packages to install",
                        default=None)

    return parser.parse_args(arguments)


def main(arguments=None):
    """Parse arguments and set up proot.

    Parse arguments, fetches initial proot distribution and downloads
    and sets up our proot.
    """
    result = _parse_arguments(arguments=arguments)

    # First fetch a proot distribution if we don't already have one
    proot_distro = _fetch_proot_distribution(result.containerdir[0])

    # Now fetch the distribution tarball itself, if we specified one
    if result.distro:
        distro_config, arch = distro.lookup(result.distro[0],
                                            result.release[0],
                                            result.arch[0])

        _print_distribution_details(distro_config, architecture)
        _fetch_distribution(result.containerdir[0],
                            proot_distro,
                            distro_config,
                            arch,
                            result.repositories,
                            result.packages)

    sys.stdout.write(colored(u"\N{check mark} "
                             "Container has been set up "
                             "in {0}\n".format(result.containerdir[0]),
                             "green",
                             attrs=["bold"]))

if __name__ == "__main__":
    main()
