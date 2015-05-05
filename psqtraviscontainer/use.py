# /psqtraviscontainer/use.py
#
# Module which handles the running of scripts and commands inside of a proot
#
# See /LICENCE.md for Copyright information
"""Module which handles the running of scripts inside of a proot."""

import os

import platform

from psqtraviscontainer import common_options
from psqtraviscontainer import linux_container


def _parse_arguments(arguments=None):
    """Return a parser context result."""
    parser = common_options.get_parser("Use")
    parser.add_argument("--cmd",
                        nargs="*",
                        help="""Command to run inside of container""",
                        default=None,
                        required=True)
    return parser.parse_args(arguments)


def main(arguments=None):
    """Select a distro in the container root and runs a command in it."""
    result = _parse_arguments(arguments=arguments)
    container_dir = os.path.realpath(result.containerdir)
    if platform.system() == "Linux":
        container = linux_container.container_for_directory(container_dir,
                                                            result)

    return container.execute(result.cmd)[0]
