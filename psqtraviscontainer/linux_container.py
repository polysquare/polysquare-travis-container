# /psqtraviscontainer/linux_container.py
#
# Abstract base class for an operating system container.
#
# See /LICENCE.md for Copyright information
"""Abstract base class for an operating system container."""

import os

import platform

import shutil

import stat

import sys

import tarfile

from collections import namedtuple

from contextlib import closing

from debian import arfile

from psqtraviscontainer import architecture
from psqtraviscontainer import common_options
from psqtraviscontainer import constants
from psqtraviscontainer import container
from psqtraviscontainer import directory
from psqtraviscontainer import distro
from psqtraviscontainer import package_system

from psqtraviscontainer.download import TemporarilyDownloadedFile

import tempdir

from termcolor import colored

_PROOT_URL_BASE = "http://static.proot.me/proot-{arch}"
_QEMU_URL_BASE = ("http://download.opensuse.org/repositories"
                  "/home:/cedric-vincent/xUbuntu_12.04/{arch}/"
                  "qemu-user-mode_1.6.1-1_{arch}.deb")


DistroConfig = distro.DistroConfig
ProotDistribution = namedtuple("ProotDistribution", "proot qemu")


def proot_distro_from_container(container_dir):
    """Return a ProotDistribution from a container dir."""
    path_to_proot_dir = constants.proot_distribution_dir(container_dir)
    path_to_proot_bin = os.path.join(path_to_proot_dir, "bin/proot")
    path_to_qemu_template = os.path.join(path_to_proot_dir,
                                         "bin/qemu-{arch}")

    def _get_qemu_binary(arch):
        """Get the qemu binary for architecture."""
        qemu_arch = architecture.Alias.qemu(arch)
        return path_to_qemu_template.format(arch=qemu_arch)

    def _get_proot_binary():
        """Get the proot binary."""
        return path_to_proot_bin

    return ProotDistribution(proot=_get_proot_binary,
                             qemu=_get_qemu_binary)


def get_dir_for_distro(container_dir, config, arch):
    """Get the distro dir in a container_dir for a DistroConfig."""
    distro_folder_name_template = (os.path.basename(config.kwargs["url"]) +
                                   ".root")
    distro_folder_name = distro_folder_name_template.format(arch=arch)
    return os.path.realpath(os.path.join(container_dir, distro_folder_name))


class LinuxContainer(container.AbstractContainer):

    """A container for a linux distribution.

    We can execute commands inside this container by using proot and qemu.
    """

    def __init__(self,  # suppress(too-many-arguments)
                 proot_distribution,
                 distro_dir,
                 release,
                 arch,
                 pkg_sys_constructor):
        """Initialize this LinuxContainer, storing its distribution config."""
        super(LinuxContainer, self).__init__()
        self._proot_distro = proot_distribution
        self._distro_dir = distro_dir
        self._arch = arch
        self._pkgsys = pkg_sys_constructor(release, arch, self)

    def _subprocess_popen_arguments(self, argv):
        """For native arguments argv, return AbstractContainer.PopenArguments.

        This returned tuple will have no environment variables set, but the
        proot command to enter this container will be prepended to the
        argv provided.
        """
        popen_args = self.__class__.PopenArguments
        proot_command = [self._proot_distro.proot(), "-S", self._distro_dir]

        # If we're not the same architecture, interpose qemu's emulator
        # for the target architecture as appropriate
        our_architecture = architecture.Alias.universal(platform.machine())
        target_architecture = architecture.Alias.universal(self._arch)

        if our_architecture != target_architecture:
            proot_command += ["-q", self._proot_distro.qemu(self._arch)]

        return popen_args(env=dict(), argv=proot_command + argv)

    def _package_system(self):
        """Return package system for this distribution."""
        return self._pkgsys


def _print_unicode_safe(text):
    """Print text to standard output, handle unicode."""
    text.encode(sys.getdefaultencoding(), "replace").decode("utf-8")
    sys.stdout.write(text)


def _extract_deb_data(archive, tmp_dir):
    """Extract archive to tmp_dir."""
    with closing(archive.getmember("data.tar.gz")) as member:
        with tarfile.open(fileobj=member,
                          mode="r|*") as data_tar:
            data_tar.extractall(path=tmp_dir)


def _fetch_proot_distribution(container_root):
    """Fetch the initial proot distribution if it is not available.

    Touches /.have-proot-distribution when complete
    """
    path_to_proot_check = constants.have_proot_distribution(container_root)
    path_to_proot_dir = constants.proot_distribution_dir(container_root)

    def _download_proot(distribution_dir, arch):
        """Download arch build of proot into distribution."""
        from psqtraviscontainer.download import download_file

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
                _print_unicode_safe(colored(("""-> Extracting {0}\n"""
                                             """""").format(qemu_deb.path()),
                                            "magenta",
                                            attrs=["bold"]))
                archive = arfile.ArFile(qemu_deb.path())
                _extract_deb_data(archive, qemu_tmp)

                qemu_binaries_path = os.path.join(qemu_tmp, "usr/bin")
                for filename in os.listdir(qemu_binaries_path):
                    shutil.copy(os.path.join(qemu_binaries_path, filename),
                                os.path.join(path_to_proot_dir, "bin"))

            shutil.rmtree(qemu_tmp)
            return os.path.join(distribution_dir, "bin", "qemu-{arch}")

    try:
        os.stat(path_to_proot_check)
        _print_unicode_safe(colored(u"""-> """
                                    """Using pre-existing proot """
                                    """distribution\n""",
                                    "green",
                                    attrs=["bold"]))

    except OSError:
        _print_unicode_safe(colored(("""Creating distribution of proot """
                                     """in {0}\n""").format(container_root),
                                    "yellow",
                                    attrs=["bold"]))

        # Distro check does not exist - create the ./_proot directory
        # and download files for this architecture
        with directory.Navigation(path_to_proot_dir):
            proot_arch = architecture.Alias.universal(platform.machine())
            qemu_arch = architecture.Alias.debian(platform.machine())
            _download_proot(path_to_proot_dir, proot_arch)
            _download_qemu(path_to_proot_dir, qemu_arch)

        with open(path_to_proot_check, "w+") as check_file:
            check_file.write("done")

        _print_unicode_safe(colored(u"""\N{check mark} """
                                    u"""Successfully installed proot """
                                    u"""distribution to """
                                    u"""{0}\n""".format(container_root),
                                    "green",
                                    attrs=["bold"]))

    return proot_distro_from_container(container_root)


def _print_distribution_details(details, distro_arch):
    """Print distribution details."""
    pkgsysname = details.pkgsys.__name__

    output = (colored("""\nConfigured Distribution:\n""",
                      "white",
                      attrs=["underline"]) +
              """ - Distribution Name: {0}\n""".format(colored(details.type,
                                                               "yellow")) +
              """ - Release: {0}\n""".format(colored(details.kwargs["release"],
                                                     "yellow")) +
              """ - Architecture: {0}\n""".format(colored(distro_arch,
                                                          "yellow")) +
              """ - Package System: {0}\n""".format(colored(pkgsysname,
                                                            "yellow")) +
              "\n")

    _print_unicode_safe(output)


def _extract_distro_archive(distro_archive_file, distro_folder):
    """Extract distribution archive into distro_folder."""
    with tarfile.open(name=distro_archive_file.path()) as archive:
        msg = ("""-> Extracting """
               """{0}\n""").format(distro_archive_file.path())
        extract_members = [m for m in archive.getmembers()
                           if not m.isdev()]
        _print_unicode_safe(colored(msg, "magenta", attrs=["bold"]))
        archive.extractall(members=extract_members, path=distro_folder)

        # Set the permissions of the extracted archive so we can delete it
        # if need be.
        os.chmod(distro_folder, os.stat(distro_folder).st_mode | stat.S_IRWXU)
        for root, directories, filenames in os.walk(distro_folder):
            for distro_folder_directory in directories:
                path = os.path.join(root, distro_folder_directory)
                try:
                    os.chmod(path, os.stat(path).st_mode | stat.S_IRWXU)
                except OSError:  # suppress(pointless-except)
                    pass
            for filename in filenames:
                path = os.path.join(root, filename)
                try:
                    os.chmod(path, os.stat(path).st_mode | stat.S_IRWXU)
                except OSError:   # suppress(pointless-except)
                    pass


def _fetch_distribution(container_root,  # pylint:disable=R0913
                        proot_distro,
                        details,
                        distro_arch,
                        repositories_path,
                        packages_path):
    """Lazy-initialize distribution and return it."""
    path_to_distro_folder = get_dir_for_distro(container_root,
                                               details,
                                               distro_arch)

    def _download_distro(details, path_to_distro_folder):
        """Download distribution and untar it in container root."""
        download_url = details.kwargs["url"].format(arch=distro_arch)
        with tempdir.TempDir() as download_dir:
            with directory.Navigation(download_dir):
                with TemporarilyDownloadedFile(download_url) as archive_file:
                    _extract_distro_archive(archive_file,
                                            path_to_distro_folder)

    # Container isn't safe to use until we've either verified that the
    # path to the distro folder exists or we've downloaded a distro into it
    linux_cont = LinuxContainer(proot_distro,
                                path_to_distro_folder,
                                details.kwargs["release"],
                                distro_arch,
                                details.pkgsys)

    try:
        os.stat(path_to_distro_folder)
        _print_unicode_safe(colored(u"""\N{check mark}  """
                                    u"""Using pre-existing folder for """
                                    u"""distro {0} {1} ({2})\n"""
                                    """""".format(details.type,
                                                  details.kwargs["release"],
                                                  distro_arch),
                                    "green",
                                    attrs=["bold"]))
    except OSError:
        # Download the distribution tarball in the distro dir
        _download_distro(details, path_to_distro_folder)

    # Now set up packages in the distribution. If more packages need
    # to be installed or the installed packages need to be updated then
    # the build cache should be cleared.
    linux_cont.install_packages(repositories_path, packages_path)

    return linux_cont


def _parse_arguments(arguments=None):
    """Return a parser context result."""
    parser = common_options.get_parser("Create")
    parser.add_argument("--repositories",
                        type=str,
                        help="""A file containing a list of repositories to """
                             """add before installing packages. Special """
                             """keywords will control the operation of this """
                             """file: \n"""
                             """{release}: The distribution release (eg, """
                             """precise)\n"""
                             """{ubuntu}: Ubuntu archive URL\n"""
                             """{launchpad}: Launchpad PPA URL header (eg,"""
                             """ppa.launchpad.net)\n""",
                        default=None)
    parser.add_argument("--packages",
                        type=str,
                        help="""A file containing a list of packages """
                             """to install""",
                        default=None)

    return parser.parse_args(arguments)


def _check_if_exists(entity):
    """Raise RuntimeError if entity does not exist."""
    if not os.path.exists(entity):
        raise RuntimeError("""A required entity {0} does not exist\n"""
                           """Try running psq-travis-container-create """
                           """first before using psq-travis-container-use."""
                           """""".format(entity))


def container_for_directory(container_dir, result):
    """Return an existing LinuxContainer at container_dir.

    Also take into account arguments in result to look up the the actual
    directory for this distro.
    """
    distro_config, arch = distro.lookup(result.distro, vars(result))

    path_to_distro_folder = get_dir_for_distro(container_dir,
                                               distro_config,
                                               arch)

    required_entities = [
        constants.have_proot_distribution(container_dir),
        path_to_distro_folder
    ]

    for entity in required_entities:
        _check_if_exists(entity)

    proot_distribution = proot_distro_from_container(container_dir)

    return LinuxContainer(proot_distribution,
                          path_to_distro_folder,
                          distro_config.kwargs["release"],
                          arch,
                          distro_config.pkgsys)


def create(container_dir, arguments):
    """Create a container using proot."""
    # First fetch a proot distribution if we don't already have one
    proot_distro = _fetch_proot_distribution(container_dir)

    # Now fetch the distribution tarball itself, if we specified one
    if arguments["distro"]:
        distro_config, arch = distro.lookup(arguments["distro"], arguments)

        _print_distribution_details(distro_config, arch)
        return _fetch_distribution(container_dir,
                                   proot_distro,
                                   distro_config,
                                   arch,
                                   arguments["repositories"],
                                   arguments["packages"])


def match(distro_config, arguments):
    """Check if distro_config_kwargs matches arguments."""
    distro_config_kwargs = distro_config.kwargs

    if platform.system() == "Linux":
        if arguments["release"] == distro_config_kwargs["release"]:
            converted = distro_config_kwargs["archfetch"](arguments["arch"])
            if converted in distro_config_kwargs["arch"]:
                return (distro_config, converted)

    return None

DISTRIBUTIONS = [  # suppress(unused-variable)
    DistroConfig(type="Ubuntu",
                 pkgsys=package_system.Dpkg,
                 constructor_func=create,
                 match_func=match,
                 kwargs={
                     "release": "precise",
                     "url": ("http://cdimage.ubuntu.com/ubuntu-core/releases/"
                             "precise/release/"
                             "ubuntu-core-12.04.5-core-{arch}.tar.gz"),
                     "arch": ["i386", "amd64", "armhf"],
                     "archfetch": architecture.Alias.debian
                 }),
    DistroConfig(type="Ubuntu",
                 pkgsys=package_system.Dpkg,
                 constructor_func=create,
                 match_func=match,
                 kwargs={
                     "release": "trusty",
                     "url": ("http://cdimage.ubuntu.com/ubuntu-core/releases/"
                             "trusty/release/"
                             "ubuntu-core-14.04.1-core-{arch}.tar.gz"),
                     "arch": ["i386", "amd64", "armhf", "powerpc"],
                     "archfetch": architecture.Alias.debian
                 }),
    DistroConfig(type="Debian",
                 pkgsys=package_system.Dpkg,
                 constructor_func=create,
                 match_func=match,
                 kwargs={
                     "release": "wheezy",
                     "url": ("http://download.openvz.org/"
                             "template/precreated/"
                             "debian-7.0-{arch}-minimal.tar.gz"),
                     "arch": ["x86", "x86_64"],
                     "archfetch": architecture.Alias.universal
                 }),
    DistroConfig(type="Debian",
                 pkgsys=package_system.Dpkg,
                 constructor_func=create,
                 match_func=match,
                 kwargs={
                     "release": "squeeze",
                     "url": ("http://download.openvz.org/"
                             "template/precreated/"
                             "debian-6.0-{arch}-minimal.tar.gz"),
                     "arch": ["x86", "x86_64"],
                     "archfetch": architecture.Alias.universal
                 }),
    DistroConfig(type="Fedora",
                 pkgsys=package_system.Yum,
                 constructor_func=create,
                 match_func=match,
                 kwargs={
                     "release": "20",
                     "url": ("http://download.openvz.org/"
                             "template/precreated/"
                             "fedora-20-{arch}.tar.gz"),
                     "arch": ["x86", "x86_64"],
                     # suppress(PYC50)
                     "archfetch": architecture.Alias.universal
                 })
]
