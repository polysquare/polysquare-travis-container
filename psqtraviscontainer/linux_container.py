# /psqtraviscontainer/linux_container.py
#
# Specialization for linux containers, using proot.
#
# See /LICENCE.md for Copyright information
"""Specialization for linux containers, using proot."""

from __future__ import unicode_literals

import errno

import os

import platform

import shutil

import stat

import tarfile

import tempfile

from collections import defaultdict
from collections import namedtuple

from getpass import getuser

from itertools import chain

from clint.textui import colored

from psqtraviscontainer import architecture
from psqtraviscontainer import constants
from psqtraviscontainer import container
from psqtraviscontainer import debian
from psqtraviscontainer import directory
from psqtraviscontainer import distro
from psqtraviscontainer import package_system
from psqtraviscontainer import printer
from psqtraviscontainer import util

from psqtraviscontainer.download import TemporarilyDownloadedFile

import tempdir

_PROOT_URL_BASE = "http://static.proot.me/proot-{arch}"
_QEMU_URL_BASE = ("http://download.opensuse.org/repositories"
                  "/home:/cedric-vincent/xUbuntu_12.04/{arch}/"
                  "qemu-user-mode_1.6.1-1_{arch}.deb")


DistroInfo = distro.DistroInfo
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


def get_dir_for_distro(container_dir, config):
    """Get the distro dir in a container_dir for a DistroConfig."""
    arch = config["arch"]
    url = config["url"]
    distro_folder_name_template = (os.path.basename(url) + ".root")
    distro_folder_name = distro_folder_name_template.format(arch=arch)
    return os.path.realpath(os.path.join(container_dir, distro_folder_name))


def _rmtrees_as_container(cont, directories):
    """Remove directories as the root user in the container.

    This allows the removal of directories where permission errors
    might not permit otherwise.
    """
    root = cont.root_filesystem_directory()

    with tempfile.NamedTemporaryFile(dir=root, mode="wt") as bash_script:
        bash_script.write(";\n".join([("rm -rf " + d) for d in directories]))
        bash_script.flush()
        cont.execute(["bash", bash_script.name], minimal_bind=True)


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

    def _subprocess_popen_arguments(self, argv, **kwargs):
        """For native arguments argv, return AbstractContainer.PopenArguments.

        This returned tuple will have no environment variables set, but the
        proot command to enter this container will be prepended to the
        argv provided.

        Pass minimal_bind=True to specify that no directories on the
        user filesystem should be exposed to the container. This will
        allow dpkg to remove certain system files in the container.
        """
        def parse_from_line(line):
            """Parse environment variable key-value pair from line."""
            return (line.split("=")[0],
                    "".join([c for c in line.split("=")[1]
                            if c != "\""]).strip())

        popen_args = self.__class__.PopenArguments

        if kwargs.get("minimal_bind", None):
            proot_command = [
                self._proot_distro.proot(),
                "-r",
                self._distro_dir,
                "-0"
            ]
        else:
            proot_command = [
                self._proot_distro.proot(),
                "-S",
                self._distro_dir
            ]

        # If we're not the same architecture, interpose qemu's emulator
        # for the target architecture as appropriate
        our_architecture = architecture.Alias.universal(platform.machine())
        target_architecture = architecture.Alias.universal(self._arch)

        if our_architecture != target_architecture:
            proot_command += ["-q", self._proot_distro.qemu(self._arch)]

        # Favor distribution's own environment variables
        with open(os.path.join(self._distro_dir, "etc", "environment")) as env:
            etc_environment_lines = env.readlines()
            prepend_env = dict([parse_from_line(l)
                                for l in etc_environment_lines
                                if l.split("=")[0].endswith("PATH")])
            overwrite_env = dict([parse_from_line(l)
                                 for l in etc_environment_lines
                                 if not l.split("=")[0].endswith("PATH")])

        # Make sure that LANG and LC_ALL are set to C, instead of
        # whatever it was set to before
        overwrite_env.update({
            "LANG": "C",
            "LC_ALL": "C"
        })

        return popen_args(prepend=prepend_env,
                          overwrite=overwrite_env,
                          argv=proot_command + argv)

    def _root_filesystem_directory(self):
        """Return directory on parent filesystem where our root is located."""
        return self._distro_dir

    def _package_system(self):
        """Return package system for this distribution."""
        return self._pkgsys

    def clean(self):
        """Clean out this container."""
        _rmtrees_as_container(self, [
            os.path.join(self._distro_dir, "tmp"),
            os.path.join(self._distro_dir, "var", "cache", "apt"),
            os.path.join(self._distro_dir, "var", "run"),
            os.path.join(self._distro_dir, "usr", "share", "doc"),
            os.path.join(self._distro_dir, "usr", "share", "locale"),
            os.path.join(self._distro_dir, "usr", "share", "man"),
            os.path.join(self._distro_dir, "var", "lib", "apt", "lists"),
            os.path.join(self._distro_dir, "dev")
        ])

        self.execute(["chown", "-R", "{}:users".format(getuser()), "/"],
                     minimal_bind=True)

        try:
            shutil.rmtree(os.path.join(self._distro_dir, "dev"))
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise error

        try:
            os.makedirs(os.path.join(self._distro_dir,
                                     "var",
                                     "cache",
                                     "apt",
                                     "archives",
                                     "partial"))
        except OSError as error:
            if error.errno != errno.EEXIST:   # suppress(PYC90)
                raise error


def _fetch_proot_distribution(container_root, target_arch):
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

    def _extract_qemu(qemu_deb_path, qemu_temp_dir):
        """Extract qemu."""
        printer.unicode_safe(colored.magenta(("""-> Extracting {0}\n"""
                                              """""").format(qemu_deb_path),
                                             bold=True))
        debian.extract_deb_data(qemu_deb_path, qemu_temp_dir)

    def _remove_unused_emulators(qemu_binaries_path):
        """Remove unused emulators from qemu distribution."""
        distributions = distro.available_distributions()
        cur_arch = platform.machine()
        archs = [d["info"].kwargs["arch"] for d in distributions]
        archs = set([architecture.Alias.qemu(a) for a in chain(*archs)
                     if a != architecture.Alias.universal(cur_arch)])
        keep_binaries = ["qemu-" + a for a in archs] + ["proot"]

        for root, _, filenames in os.walk(qemu_binaries_path):
            for filename in filenames:
                if os.path.basename(filename) not in keep_binaries:
                    os.remove(os.path.join(root, filename))

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
                qemu_binaries_path = os.path.join(qemu_tmp, "usr", "bin")
                _extract_qemu(qemu_deb.path(), qemu_tmp)
                _remove_unused_emulators(qemu_binaries_path)

                for filename in os.listdir(qemu_binaries_path):
                    shutil.copy(os.path.join(qemu_binaries_path, filename),
                                os.path.join(path_to_proot_dir, "bin"))

            shutil.rmtree(qemu_tmp)

        return os.path.join(distribution_dir, "bin", "qemu-{arch}")

    try:
        os.stat(path_to_proot_check)
        printer.unicode_safe(colored.green("""-> """
                                           """Using pre-existing proot """
                                           """distribution\n""",
                                           bold=True))

    except OSError:
        create_msg = """Creating distribution of proot in {}\n"""
        root_relative = os.path.relpath(container_root)
        printer.unicode_safe(colored.yellow(create_msg.format(root_relative),
                                            bold=True))

        # Distro check does not exist - create the ./_proot directory
        # and download files for this architecture
        with directory.Navigation(path_to_proot_dir):
            proot_arch = architecture.Alias.universal(platform.machine())
            _download_proot(path_to_proot_dir, proot_arch)

            # We may not need qemu if we're not going to emulate
            # anything.
            if (architecture.Alias.universal(platform.machine()) !=
                    architecture.Alias.universal(target_arch) or
                    os.environ.get("_FORCE_DOWNLOAD_QEMU", None)):
                qemu_arch = architecture.Alias.debian(platform.machine())
                _download_qemu(path_to_proot_dir, qemu_arch)

        with open(path_to_proot_check, "w+") as check_file:
            check_file.write("done")

        printer.unicode_safe(colored.green("""\N{check mark} """
                                           """Successfully installed proot """
                                           """distribution to """
                                           """{}\n""".format(root_relative),
                                           bold=True))

    return proot_distro_from_container(container_root)


def _extract_distro_archive(distro_archive_file, distro_folder):
    """Extract distribution archive into distro_folder."""
    with tarfile.open(name=distro_archive_file.path()) as archive:
        msg = ("""-> Extracting """
               """{0}\n""").format(os.path.relpath(distro_archive_file.path()))
        extract_members = [m for m in archive.getmembers()
                           if not m.isdev()]
        printer.unicode_safe(colored.magenta(msg, bold=True))
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
                        details):
    """Lazy-initialize distribution and return it."""
    path_to_distro_folder = get_dir_for_distro(container_root,
                                               details)

    def _download_distro(details, path_to_distro_folder):
        """Download distribution and untar it in container root."""
        distro_arch = details["arch"]
        download_url = details["url"].format(arch=distro_arch)
        with tempdir.TempDir() as download_dir:
            with directory.Navigation(download_dir):
                with TemporarilyDownloadedFile(download_url) as archive_file:
                    _extract_distro_archive(archive_file,
                                            path_to_distro_folder)

    def _minimize_ubuntu(cont):
        """Reduce the install footprint of ubuntu as much as possible."""
        required_packages = {
            "precise": set([
                "apt",
                "base-files",
                "base-passwd",
                "bash",
                "bsdutils",
                "coreutils",
                "dash",
                "debconf",
                "debianutils",
                "diffutils",
                "dpkg",
                "findutils",
                "gcc-4.6-base",
                "gnupg",
                "gpgv",
                "grep",
                "gzip",
                "libacl1",
                "libapt-pkg4.12",
                "libattr1",
                "libbz2-1.0",
                "libc-bin",
                "libc6",
                "libdb5.1",
                "libffi6",
                "libgcc1",
                "liblzma5",
                "libpam-modules",
                "libpam-modules-bin",
                "libpam-runtime",
                "libpam0g",
                "libreadline6",
                "libselinux1",
                "libstdc++6",
                "libtinfo5",
                "libusb-0.1-4",
                "makedev",
                "mawk",
                "multiarch-support",
                "perl-base",
                "readline-common",
                "sed",
                "sensible-utils",
                "tar",
                "tzdata",
                "ubuntu-keyring",
                "xz-utils",
                "zlib1g"
            ]),
            "trusty": set([
                "apt",
                "base-files",
                "base-passwd",
                "bash",
                "bsdutils",
                "coreutils",
                "dash",
                "debconf",
                "debianutils",
                "diffutils",
                "dh-python",
                "dpkg",
                "findutils",
                "gcc-4.8-base",
                "gcc-4.9-base",
                "gnupg",
                "gpgv",
                "grep",
                "gzip",
                "libacl1",
                "libapt-pkg4.12",
                "libaudit1",
                "libaudit-common",
                "libattr1",
                "libbz2-1.0",
                "libc-bin",
                "libc6",
                "libcap2",
                "libdb5.3",
                "libdebconfclient0",
                "libexpat1",
                "libmpdec2",
                "libffi6",
                "libgcc1",
                "liblzma5",
                "libncursesw5",
                "libpcre3",
                "libpam-modules",
                "libpam-modules-bin",
                "libpam-runtime",
                "libpam0g",
                "libpython3-stdlib",
                "libpython3.4-stdlib",
                "libpython3",
                "libpython3-minimal",
                "libpython3.4",
                "libpython3.4-minimal",
                "libreadline6",
                "libselinux1",
                "libssl1.0.0",
                "libstdc++6",
                "libsqlite3-0",
                "libtinfo5",
                "libusb-0.1-4",
                "lsb-release",
                "makedev",
                "mawk",
                "mime-support",
                "multiarch-support",
                "perl-base",
                "python3",
                "python3-minimal",
                "python3.4",
                "python3.4-minimal",
                "readline-common",
                "sed",
                "sensible-utils",
                "tar",
                "tzdata",
                "ubuntu-keyring",
                "xz-utils",
                "zlib1g"
            ])
        }

        os.environ["SUDO_FORCE_REMOVE"] = "yes"
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"

        pkgs = set(cont.execute(["dpkg-query",
                                 "-Wf",
                                 "${Package} "])[1].split(" "))
        release = details["release"]
        remove = [l for l in list(pkgs ^ required_packages[release]) if len(l)]

        if len(remove):
            cont.execute_success(["dpkg",
                                  "--purge",
                                  "--force-all"] + remove,
                                 minimal_bind=True)

        with open(os.path.join(get_dir_for_distro(container_root,
                                                  details),
                               "etc",
                               "apt",
                               "apt.conf.d",
                               "99container"), "w") as apt_config:
            apt_config.write("\n".join([
                "APT::Install-Recommends \"0\";",
                "APT::Install-Suggests \"0\";"
            ]))

    # Container isn't safe to use until we've either verified that the
    # path to the distro folder exists or we've downloaded a distro into it
    linux_cont = LinuxContainer(proot_distro,
                                path_to_distro_folder,
                                details["release"],
                                details["arch"],
                                details["pkgsys"])

    try:
        os.stat(path_to_distro_folder)
        use_existing_msg = ("""\N{check mark} Using existing folder for """
                            """proot distro """
                            """{distro} {release} {arch}\n""")
        printer.unicode_safe(colored.green(use_existing_msg.format(**details),
                                           bold=True))
    except OSError:
        # Download the distribution tarball in the distro dir
        _download_distro(details, path_to_distro_folder)

        # Minimize the installed distribution, but only when it
        # was just initially downloaded
        minimize_actions = defaultdict(lambda: lambda c: None,
                                       Ubuntu=_minimize_ubuntu)
        minimize_actions[details["distro"]](linux_cont)

    return linux_cont


def container_for_directory(container_dir, distro_config):
    """Return an existing LinuxContainer at container_dir for distro_config.

    Also take into account arguments in result to look up the the actual
    directory for this distro.
    """
    path_to_distro_folder = get_dir_for_distro(container_dir,
                                               distro_config)

    required_entities = [
        constants.have_proot_distribution(container_dir),
        path_to_distro_folder
    ]

    for entity in required_entities:
        util.check_if_exists(entity)

    proot_distribution = proot_distro_from_container(container_dir)

    return LinuxContainer(proot_distribution,
                          path_to_distro_folder,
                          distro_config["release"],
                          distro_config["arch"],
                          distro_config["pkgsys"])


def create(container_dir, distro_config):
    """Create a container using proot."""
    # First fetch a proot distribution if we don't already have one
    proot_distro = _fetch_proot_distribution(container_dir,
                                             distro_config["arch"])

    # Now fetch the distribution tarball itself, if we specified one
    cont = _fetch_distribution(container_dir,
                               proot_distro,
                               distro_config)

    return cont


def _info_with_arch_to_config(info, arch):
    """Convert selected architecture for DistroInfo into DistroConfig."""
    config = info.kwargs.copy()

    del config["arch"]
    del config["archfetch"]

    config["arch"] = arch

    return config


def _valid_archs(archs):
    """Return valid archs to emulate from archs.

    64 bit architectures can't be emulated on a 32 bit system, so remove
    them form the list of valid architectures.
    """
    blacklist = defaultdict(lambda: None)
    blacklist["x86"] = "x86_64"
    blacklist["x86_64"] = "x86"

    arch_alias = architecture.Alias.universal
    machine = arch_alias(platform.machine())

    return [a for a in archs if arch_alias(a) != blacklist[machine]]


def match(info, arguments):
    """Check if info matches arguments."""
    if platform.system() != "Linux":
        return None

    if arguments.get("distro", None) != info.kwargs["distro"]:
        return None

    if arguments.get("local", None):
        return None

    distro_release = info.kwargs["release"]

    # pychecker thinks that a list comprehension as a return value is
    # always None.
    distro_archs = _valid_archs(info.kwargs["arch"])  # suppress(PYC90)
    distro_archfetch = info.kwargs["archfetch"]

    if arguments.get("release", None) == distro_release:
        converted = distro_archfetch(arguments.get("arch", None))
        if converted in distro_archs:
            return _info_with_arch_to_config(info, converted)

    return None


def enumerate_all(info):
    """Enumerate all valid configurations for this DistroInfo."""
    if platform.system() != "Linux":
        return

    for arch in _valid_archs(info.kwargs["arch"]):  # suppress(PYC90)
        yield _info_with_arch_to_config(info, arch)


class LinuxInfo(DistroInfo):
    """Linux-specific specialization of DistroInfo."""

    PACKAGE_SYSTEMS = {
        "Ubuntu": package_system.Dpkg,
        "Debian": package_system.Dpkg,
        "Fedora": package_system.Yum
    }

    def __new__(cls, distro_type, **kwargs):
        """Create DistroInfo namedtuple using provided arguments."""
        kwargs.update({
            "distro": distro_type,
            "pkgsys": LinuxInfo.PACKAGE_SYSTEMS[distro_type],
            "installation": "proot"
        })

        return DistroInfo.__new__(cls,
                                  create_func=create,
                                  get_func=container_for_directory,
                                  match_func=match,
                                  enumerate_func=enumerate_all,
                                  kwargs=kwargs)

DISTRIBUTIONS = [  # suppress(unused-variable)
    LinuxInfo("Ubuntu",
              release="precise",
              url=("http://old-releases.ubuntu.com/releases/ubuntu-core/"
                   "releases/12.04.3/release/"
                   "ubuntu-core-12.04.3-core-{arch}.tar.gz"),
              arch=["i386", "amd64", "armhf"],
              archfetch=architecture.Alias.debian),
    LinuxInfo("Ubuntu",
              release="trusty",
              url=("http://old-releases.ubuntu.com/releases/ubuntu-core/"
                   "releases/utopic/release/"
                   "ubuntu-core-14.10-core-{arch}.tar.gz"),
              arch=["i386", "amd64", "armhf", "powerpc"],
              archfetch=architecture.Alias.debian),
    LinuxInfo("Debian",
              release="wheezy",
              url=("http://download.openvz.org/"
                   "template/precreated/debian-7.0-{arch}-minimal.tar.gz"),
              arch=["x86", "x86_64"],
              archfetch=architecture.Alias.universal),
    LinuxInfo("Debian",
              release="squeeze",
              url=("http://download.openvz.org/"
                   "template/precreated/debian-6.0-{arch}-minimal.tar.gz"),
              arch=["x86", "x86_64"],
              archfetch=architecture.Alias.universal),
    LinuxInfo("Fedora",
              release="20",
              url=("http://download.openvz.org/"
                   "template/precreated/fedora-20-{arch}.tar.gz"),
              arch=["x86", "x86_64"],
              # suppress(PYC50)
              archfetch=architecture.Alias.universal)
]
