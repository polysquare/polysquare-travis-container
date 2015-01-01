# /psqtraviscontainer/use.py
#
# Module which handles the running of scripts and commands inside of a proot
#
# See LICENCE.md for Copyright information
""" Module which handles the running of scripts inside of a proot."""

import os

import platform

import subprocess

from collections import namedtuple

from psqtraviscontainer import architecture
from psqtraviscontainer import common_options
from psqtraviscontainer import constants
from psqtraviscontainer import distro

ProotDistribution = namedtuple("ProotDistribution", "proot qemu")


class PtraceRootExecutor(object):

    """For a distro configured a in container, a mechanism to execute code."""

    def __init__(self, proot_distro, container_root, config, arch):
        """Initialize PtraceRootExecutor for container and distro."""
        super(PtraceRootExecutor, self).__init__()
        self._proot_distro = proot_distro
        self._container_root = container_root
        self._config = config
        self._arch = arch

    def _execute_argv(self, user_argv):
        """Get argv to pass to subprocess later."""
        distro_dir = distro.get_dir(self._container_root,
                                    self._config,
                                    self._arch)
        proot_command = [self._proot_distro.proot(), "-S", distro_dir]

        # If we're not the same architecture, interpose qemu's emulator
        # for the target architecture as appropriate
        our_architecture = architecture.Alias.universal(platform.machine())
        target_architecture = architecture.Alias.universal(self._arch)

        if our_architecture != target_architecture:
            proot_command += ["-q", self._proot_distro.qemu(self._arch)]

        return proot_command + user_argv

    def execute(self, argv):
        """Execute the command specified by argv, return exit status."""
        return subprocess.call(self._execute_argv(argv))

    def execute_success(self, argv):
        """Execute the command specified by argv, throws on failure."""
        subprocess.check_call(self._execute_argv(argv))


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


def _parse_arguments(arguments=None):
    """Return a parser context result."""
    parser = common_options.get_parser("Use")
    parser.add_argument("--cmd",
                        nargs="*",
                        help="Command to run inside of container",
                        default=None,
                        required=True)
    return parser.parse_args(arguments)


def _check_if_exists(entity):
    """Raise RuntimeError if entity does not exist."""
    if not os.path.exists(entity):
        raise RuntimeError("A required entity {0} does not exist\n"
                           "Try running psq-travis-container-create "
                           "first before using psq-travis-container-use.")


def main(arguments=None):
    """Select a distro in the container root and runs a comamnd in it."""
    result = _parse_arguments(arguments=arguments)
    distro_config, arch = distro.lookup(result.distro[0],
                                        result.release[0],
                                        result.arch[0])
    required_entities = [
        constants.have_proot_distribution(result.containerdir[0]),
        distro.get_dir(result.containerdir[0], distro_config, arch)
    ]

    for entity in required_entities:
        _check_if_exists(entity)

    # Now create an executor and run our command
    proot_distro = proot_distro_from_container(result.containerdir[0])
    proot_executor = PtraceRootExecutor(proot_distro,
                                        result.containerdir[0],
                                        distro_config,
                                        arch)

    return proot_executor.execute(result.cmd)
