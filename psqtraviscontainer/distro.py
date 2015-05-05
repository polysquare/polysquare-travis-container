# /psqtraviscontainer/distro.py
#
# Module in which all configurations for various distributions are stored.
#
# See /LICENCE.md for Copyright information
"""Various distribution configurations are stored here."""

from collections import namedtuple


DistroConfig = namedtuple("DistroConfig",
                          "type constructor_func match_func kwargs pkgsys")


def available_distributions():
    """Return list of available distributions."""
    from psqtraviscontainer import linux_container

    return linux_container.DISTRIBUTIONS


def lookup(distro_type, arguments):
    """Look up DistroConfig by matching against its name and arguments."""
    matched_distribution = (None, None)

    for distribution in available_distributions():
        if distribution.type == distro_type:
            matched_distribution = distribution.match_func(distribution,
                                                           arguments)
            if matched_distribution:
                return matched_distribution

    raise RuntimeError("Couldn't find matching distribution "
                       "{0} ({1})".format(distro_type, repr(arguments)))
