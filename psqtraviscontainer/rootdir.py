# /psqtraviscontainer/rootdir.py
#
# Print the root directory of a selected container to standard out.
#
# See /LICENCE.md for Copyright information
"""Print the root directory of a selected container to standard out."""

import os

import sys

from psqtraviscontainer import common_options
from psqtraviscontainer import distro


def main(arguments=None):
    """Get container and print root filesystem directory."""
    parser = common_options.get_parser("""Get root directory for""")
    result = parser.parse_args(arguments)
    container_dir = os.path.realpath(result.containerdir)

    selected_distro = distro.lookup(vars(result))

    # Get the selected distribution's container and print its root
    # filesystem directory
    with selected_distro["info"].get_func(container_dir,
                                          selected_distro) as container:
        sys.stdout.write(container.root_filesystem_directory())

if __name__ == "__main__":
    main()
