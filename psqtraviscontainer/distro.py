# /psqtraviscontainer/distro.py
#
# Module in which all configurations for various distributions are stored.
#
# See /LICENCE.md for Copyright information
"""Various distribution configurations are stored here."""

import errno

import itertools

import json

import os

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


class NoDistributionDetailsError(Exception):
    """An exception that is raised if there is no distribution in a path."""

    pass


def read_existing(container_dir):
    """Attempt to detect an existing distribution in container_dir."""
    try:
        with open(os.path.join(container_dir, ".distroinfo")) as distroinfo_f:
            return json.load(distroinfo_f)
    except EnvironmentError as error:
        if error.errno == errno.ENOENT:
            raise NoDistributionDetailsError()
        else:
            raise error


def write_details(container_dir, selected_distro):
    """Write details of selected_distro to container_dir."""
    with open(os.path.join(container_dir, ".distroinfo"), "w") as info_f:
        keys = ("distro", "installation", "arch", "release")
        info_f.write(json.dumps({
            k: v for k, v in selected_distro.items()
            if k in keys
        }))


def _search_for_matching_distro(distro_info):
    """Check all known distributions for one matching distro_info."""
    matched_distribution = None

    for distribution in _distribution_information():
        matched_distribution = distribution.match_func(distribution,
                                                       distro_info)
        if matched_distribution:
            matched_distribution["info"] = distribution
            return matched_distribution


def lookup(arguments):
    """Look up DistroConfig by matching against its name and arguments."""
    matched_distribution = _search_for_matching_distro(arguments)
    if matched_distribution:
        return matched_distribution

    # As last resort, look inside the container directory and see if there
    # is something in there that we know about.
    if arguments.get("containerdir", None):
        try:
            distro_info = read_existing(arguments["containerdir"])
            matched_distribution = _search_for_matching_distro(distro_info)

            if matched_distribution:
                return matched_distribution
        except NoDistributionDetailsError:  # suppress(pointless-except)
            pass

    raise RuntimeError("""Couldn't find matching distribution """
                       """({0})""".format(repr(arguments)))
