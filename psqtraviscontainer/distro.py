# /psqtraviscontainer/distro.py
#
# Module in which all configurations for various distributions are stored.
#
# See /LICENCE.md for Copyright information
"""Various distribution configurations are stored here."""

import os

from collections import namedtuple

from psqtraviscontainer import architecture
from psqtraviscontainer import package_system

DistroConfig = namedtuple("DistroConfig",
                          "type release url archs pkgsys archfetch")

AVAILABLE_DISTRIBUTIONS = [
    DistroConfig(type="Ubuntu",
                 release="precise",
                 url="http://cdimage.ubuntu.com/ubuntu-core/releases/precise/release/ubuntu-core-12.04.5-core-{arch}.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["i386", "amd64", "armhf"],
                 pkgsys=package_system.Dpkg,
                 archfetch=architecture.Alias.debian),
    DistroConfig(type="Ubuntu",
                 release="trusty",
                 url="http://cdimage.ubuntu.com/ubuntu-core/releases/trusty/release/ubuntu-core-14.04.1-core-{arch}.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["i386", "amd64", "armhf", "powerpc"],
                 pkgsys=package_system.Dpkg,
                 archfetch=architecture.Alias.debian),
    DistroConfig(type="Debian",
                 release="wheezy",
                 url="http://download.openvz.org/template/precreated/debian-7.0-{arch}-minimal.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["x86", "x86_64"],
                 pkgsys=package_system.Dpkg,
                 archfetch=architecture.Alias.universal),
    DistroConfig(type="Debian",
                 release="squeeze",
                 url="http://download.openvz.org/template/precreated/debian-6.0-{arch}-minimal.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["x86", "x86_64"],
                 pkgsys=package_system.Dpkg,
                 archfetch=architecture.Alias.universal),
    DistroConfig(type="Fedora",
                 release="20",
                 url="http://download.openvz.org/template/precreated/fedora-20-{arch}.tar.gz",  # NOQA # pylint:disable=line-too-long
                 archs=["x86", "x86_64"],
                 pkgsys=package_system.Yum,
                 archfetch=architecture.Alias.universal)
]


def lookup(distro_type, distro_release, distro_arch):
    """Look up DistroConfig by type, release and arch.

    If a match for both distro_type and distro_release is found, we check
    that distro_arch is in the list of supported architectures for this
    distribution. If not we return None.
    """
    for distribution in AVAILABLE_DISTRIBUTIONS:
        if (distribution.type == distro_type and
                distribution.release == distro_release):
            converted_distro_arch = distribution.archfetch(distro_arch)
            if converted_distro_arch in distribution.archs:
                return (distribution, converted_distro_arch)

    raise RuntimeError("Couldn't find matching distribution "
                       "{0} {1} ({2})".format(distro_type,
                                              distro_release,
                                              distro_arch))


def get_dir(container_dir, config, arch):
    """Get the distro dir in a container_dir for a DistroConfig."""
    distro_folder_name_template = os.path.basename(config.url) + ".root"
    distro_folder_name = distro_folder_name_template.format(arch=arch)
    return os.path.join(container_dir, distro_folder_name)
