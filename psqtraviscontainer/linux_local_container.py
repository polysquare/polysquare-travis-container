# /psqtraviscontainer/linux_local_container.py
#
# Specialization for linux containers, using a variant
# of linux_container. This variant uses proot to set
# up the container, but installs packages into a
# separate directory and makes them available using
# paths.
#
# See /LICENCE.md for Copyright information
"""Specialization for linux containers, using proot."""

from __future__ import unicode_literals

import os

import platform

from psqtraviscontainer import architecture
from psqtraviscontainer import container
from psqtraviscontainer import distro
from psqtraviscontainer import linux_container
from psqtraviscontainer import package_system


DistroInfo = distro.DistroInfo
DistroConfig = distro.DistroConfig


def get_dir_for_distro(container_dir, config):
    """Get the distro dir in a container_dir for a DistroConfig."""
    arch = config["arch"]
    url = config["url"]
    distro_folder_name_template = (os.path.basename(url) + ".root")
    distro_folder_name = distro_folder_name_template.format(arch=arch)
    return os.path.realpath(os.path.join(container_dir, distro_folder_name))


class LocalLinuxContainer(container.AbstractContainer):
    """A container for a linux distribution.

    We can execute commands inside this container by using proot and qemu.
    """

    def __init__(self,  # suppress(too-many-arguments)
                 linux_cont,
                 package_root,
                 release,
                 arch,
                 pkg_sys_constructor):
        """Initialize this LocalLinuxContainer, storing its distro config."""
        super(LocalLinuxContainer, self).__init__()
        self._linux_cont = linux_cont
        self._arch = arch
        self._package_root = package_root
        self._pkgsys = pkg_sys_constructor(release, arch, self)

    def _root_filesystem_directory(self):
        """Return directory on parent filesystem where our root is located."""
        return self._package_root

    def _package_system(self):
        """Return package system for this distribution."""
        return self._pkgsys

    def _subprocess_popen_arguments(self, argv, **kwargs):
        """For native arguments argv, return AbstractContainer.PopenArguments.

        This returned tuple will have no environment variables set, but the
        proot command to enter this container will be prepended to the
        argv provided.

        Set the requires_full_access keyword to run this command through the
        proot wrapper.
        """
        if kwargs.get("requires_full_access", None):
            # suppress(protected-access)
            return self._linux_cont._subprocess_popen_arguments(argv,
                                                                **kwargs)

        popen_args = self.__class__.PopenArguments
        prepend_env = {
            "LD_LIBRARY_PATH": os.pathsep.join([
                os.path.join(self._package_root,
                             "usr",
                             "lib",
                             "x86_64-linux-gnu"),
                os.path.join(self._package_root,
                             "usr",
                             "lib",
                             "i686-linux-gnu"),
                os.path.join(self._package_root,
                             "usr",
                             "lib")
            ]),
            "PKG_CONFIG_PATH": os.pathsep.join([
                os.path.join(self._package_root,
                             "usr",
                             "lib",
                             "pkgconfig"),
                os.path.join(self._package_root,
                             "usr",
                             "lib",
                             "x86_64-linux-gnu",
                             "pkgconfig"),
                os.path.join(self._package_root,
                             "usr",
                             "lib",
                             "i686-linux-gnu",
                             "pkgconfig")
            ]),
            "PATH": os.pathsep.join([
                os.path.join(self._package_root,
                             "usr",
                             "bin")
            ])
        }

        return popen_args(prepend=prepend_env,
                          overwrite=dict(),
                          argv=argv)

    def clean(self):
        """Clean out this container."""
        self._linux_cont.clean()


def container_for_directory(container_dir, distro_config):
    """G an existing LocalLinuxContainer at container_dir for distro_config.

    Also take into account arguments in result to look up the the actual
    directory for this distro.
    """
    cont = linux_container.container_for_directory(container_dir,
                                                   distro_config)
    path_to_distro_folder = get_dir_for_distro(container_dir,
                                               distro_config)

    return LocalLinuxContainer(cont,
                               os.path.join(path_to_distro_folder,
                                            "packages"),
                               distro_config["release"],
                               distro_config["arch"],
                               distro_config["pkgsys"])


def create(container_dir, distro_config):
    """Create a container using proot."""
    cont = linux_container.create(container_dir, distro_config)
    path_to_distro_folder = get_dir_for_distro(container_dir,
                                               distro_config)

    return LocalLinuxContainer(cont,
                               os.path.join(path_to_distro_folder,
                                            "packages"),
                               distro_config["release"],
                               distro_config["arch"],
                               distro_config["pkgsys"])


def _info_with_arch_to_config(info, arch):
    """Convert selected architecture for DistroInfo into DistroConfig."""
    config = info.kwargs.copy()

    del config["arch"]
    del config["archfetch"]

    config["arch"] = arch

    return config


def _valid_archs(archs):
    """Return valid archs to emulate from archs."""
    alias = architecture.Alias.universal(platform.machine())
    return [a for a in archs
            if architecture.Alias.universal(a) == alias]


def match(info, arguments):
    """Check if info matches arguments."""
    if platform.system() != "Linux":
        return None

    if arguments.get("distro", None) != info.kwargs["distro"]:
        return None

    if not arguments.get("local", None):
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


class LinuxLocalInfo(DistroInfo):
    """Linux-specific specialization of DistroInfo."""

    PACKAGE_SYSTEMS = {
        "Ubuntu": package_system.DpkgLocal,
    }

    def __new__(cls, distro_type, **kwargs):
        """Create DistroInfo tuple using provided arguments."""
        kwargs.update({
            "distro": distro_type,
            "pkgsys": LinuxLocalInfo.PACKAGE_SYSTEMS[distro_type],
            "installation": "local"
        })

        return DistroInfo.__new__(cls,
                                  create_func=create,
                                  get_func=container_for_directory,
                                  match_func=match,
                                  enumerate_func=enumerate_all,
                                  kwargs=kwargs)

DISTRIBUTIONS = [  # suppress(unused-variable)
    LinuxLocalInfo("Ubuntu",
                   release="precise",
                   url=("http://old-releases.ubuntu.com/releases/ubuntu-core/"
                        "releases/12.04.3/release/"
                        "ubuntu-core-12.04.3-core-{arch}.tar.gz"),
                   arch=["i386", "amd64", "armhf"],
                   archfetch=architecture.Alias.debian,),
    LinuxLocalInfo("Ubuntu",
                   release="trusty",
                   url=("http://old-releases.ubuntu.com/releases/ubuntu-core/"
                        "releases/utopic/release/"
                        "ubuntu-core-14.10-core-{arch}.tar.gz"),
                   arch=["i386", "amd64", "armhf", "powerpc"],
                   archfetch=architecture.Alias.debian)
]
