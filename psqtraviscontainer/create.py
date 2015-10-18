# /psqtraviscontainer/create.py
#
# Module which handles the creation of proot in which APT packages
# can be readily installed
#
# See /LICENCE.md for Copyright information
"""Module which handles the creation of proot.

The proot for a distribution is a special directory entered with the proot
command, which behaves like a chroot, except that no root access is required
in order to create the jail. Commands running in the proot will have filesystem
requests redirected to the proot and believe that they are running as uid 0
"""

from __future__ import unicode_literals

import os

from clint.textui import colored

from psqtraviscontainer import common_options
from psqtraviscontainer import distro
from psqtraviscontainer import printer

from psqtraviscontainer.architecture import Alias


def _print_distribution_details(details):
    """Print distribution details."""
    def _y_v(value):
        """Print value in distribution details."""
        return colored.yellow(value)

    # Maps keys in configuration to a pretty-printable name.
    distro_pretty_print_map = {
        "distro": lambda v: """Distribution Name: """ + _y_v(v),
        "release": lambda v: """Release: """ + _y_v(v),
        "arch": lambda v: """Architecture: """ + _y_v(Alias.universal(v)),
        "pkgsys": lambda v: """Package System: """ + _y_v(v.__name__),
    }

    output = bytearray()
    output += ("\n" +
               colored.white("""Configured Distribution:""", bold=True) +
               "\n").encode()

    for key, value in details.items():
        if key in distro_pretty_print_map:
            line = " - {0}\n".format(distro_pretty_print_map[key](value))
            output += line.encode()

    output += "\n".encode()

    printer.unicode_safe(output.decode("utf-8"))


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


def main(arguments=None):
    """Parse arguments and set up proot.

    Parse arguments, fetches initial proot distribution and downloads
    and sets up our proot.
    """
    result = _parse_arguments(arguments=arguments)
    container_dir = os.path.realpath(result.containerdir)

    selected_distro = distro.lookup(vars(result))

    _print_distribution_details(selected_distro)

    # Now set up packages in the distribution. If more packages need
    # to be installed or the installed packages need to be updated then
    # the build cache should be cleared.
    with selected_distro["info"].create_func(container_dir,
                                             selected_distro) as container:
        container.install_packages(result.repositories, result.packages)

    relative_containerdir = os.path.relpath(result.containerdir)
    msg = """\N{check mark} Container has been set up in {0}\n"""
    printer.unicode_safe(colored.green(msg.format(relative_containerdir),
                                       bold=True))

if __name__ == "__main__":
    main()
