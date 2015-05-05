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

import os

import platform

import sys

from psqtraviscontainer import common_options
from psqtraviscontainer import linux_container

from termcolor import colored


def _print_unicode_safe(text):
    """Print text to standard output, handle unicode."""
    text.encode(sys.getdefaultencoding(), "replace").decode("utf-8")
    sys.stdout.write(text)


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

    if platform.system() == "Linux":
        linux_container.create(os.path.realpath(result.containerdir),
                               vars(result))

    _print_unicode_safe(colored(u"""\N{check mark}  """
                                u"""Container has been set up """
                                u"""in {0}\n""".format(result.containerdir),
                                "green",
                                attrs=["bold"]))

if __name__ == "__main__":
    main()
