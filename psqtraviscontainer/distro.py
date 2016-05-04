# /psqtraviscontainer/distro.py
#
# Module in which all configurations for various distributions are stored.
#
# See /LICENCE.md for Copyright information
"""Various distribution configurations are stored here."""

import itertools

from collections import namedtuple


DistroConfig = dict
DistroInfo = namedtuple("DistroInfo",
                        "create_func "
                        "get_func "
                        "match_func "
                        "enumerate_func "
                        "kwargs")


def _distribution_information():
    """Return generator of DistroInfo."""
    from psqtraviscontainer import linux_container
    from psqtraviscontainer import linux_local_container
    from psqtraviscontainer import osx_container
    from psqtraviscontainer import windows_container

    return itertools.chain(linux_local_container.DISTRIBUTIONS,
                           linux_container.DISTRIBUTIONS,
                           osx_container.DISTRIBUTIONS,
                           windows_container.DISTRIBUTIONS)


def available_distributions():
    """Return list of available distributions."""
    for info in _distribution_information():
        for config in info.enumerate_func(info):
            config["info"] = info
            config = config.copy()
            yield config


def lookup(arguments):
    """Look up DistroConfig by matching against its name and arguments."""
    matched_distribution = None

    for distribution in _distribution_information():
        matched_distribution = distribution.match_func(distribution,
                                                       arguments)
        if matched_distribution:
            matched_distribution["info"] = distribution
            return matched_distribution

    raise RuntimeError("""Couldn't find matching distribution """
                       """({0})""".format(repr(arguments)))
