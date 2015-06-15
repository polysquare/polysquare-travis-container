# /psqtraviscontainer/use.py
#
# Module which handles the running of scripts and commands inside of a proot
#
# See /LICENCE.md for Copyright information
"""Module which handles the running of scripts inside of a proot."""

import os

import sys

from psqtraviscontainer import common_options
from psqtraviscontainer import distro


def _parse_arguments(arguments=None):
    """Return a parser context result."""
    parser = common_options.get_parser("Use")
    parser.add_argument("--show-output",
                        action="store_true",
                        help="""Show output of commands once they've run.""")
    return parser.parse_args(arguments)


def main(arguments=None):
    """Select a distro in the container root and runs a command in it."""
    arguments = (arguments or sys.argv[1:])

    try:
        two_dashes_argument = arguments.index("--")
    except ValueError:
        sys.stdout.write("""Command line must specify command to """
                         """run with two dashes\n""")
        sys.exit(1)

    parseable_arguments = arguments[:two_dashes_argument]
    command = arguments[two_dashes_argument + 1:]

    argparse_result = _parse_arguments(arguments=parseable_arguments)

    container_dir = os.path.realpath(argparse_result.containerdir)
    selected_distro = distro.lookup(vars(argparse_result))
    with selected_distro["info"].get_func(container_dir,
                                          selected_distro) as container:
        if argparse_result.show_output:
            execute_kwargs = {
                "stderr": None,
                "stdout": None
            }
        else:
            execute_kwargs = dict()

        result = container.execute(command, **execute_kwargs)[0]

    return result
