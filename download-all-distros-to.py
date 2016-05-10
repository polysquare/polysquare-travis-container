# /download-all-distros-to.py
#
# Helper script to download all linux distributions
#
# See /LICENCE.md for Copyright information
"""Specialization for linux containers, using proot."""

import psqtraviscontainer.architecture
import psqtraviscontainer.distro

from test.testutil import download_file_cached

for distro in psqtraviscontainer.distro.available_distributions():
    if (not distro.get("arch", None) or
            not distro.get("info", None).kwargs.get("archfetch", None)):
        continue
    archfetch = distro["info"].kwargs["archfetch"]
    download_file_cached(distro["url"].format(arch=distro["arch"]))
