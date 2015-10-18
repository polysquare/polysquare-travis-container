# /test/test_unit.py
#
# Unit tests for various utilities.
#
# See /LICENCE.md for Copyright information
"""Unit tests for various utilities."""

import os

import shutil

from psqtraviscontainer import architecture
from psqtraviscontainer import directory
from psqtraviscontainer import distro

from testtools import ExpectedException
from testtools import TestCase

from testtools.matchers import AllMatch
from testtools.matchers import DirExists
from testtools.matchers import MatchesPredicate


class TestDirectoryNavigation(TestCase):
    """Tests for psqtraviscontainer/directory.py."""

    def test_enter_create_dir(self):
        """Check that we create a dir when entering a non-existent one."""
        does_not_exist = os.path.join(os.getcwd(), "does_not_exist")
        self.addCleanup(lambda: shutil.rmtree(does_not_exist))
        with directory.Navigation(does_not_exist) as entered:
            self.assertThat(entered, DirExists())

    def test_enter_exist_dir(self):
        """Check that we can enter an existing dir."""
        existing_dir = os.path.join(os.getcwd(), "existing")
        os.makedirs(existing_dir)
        self.addCleanup(lambda: shutil.rmtree(existing_dir))
        with directory.Navigation(existing_dir) as entered:
            self.assertThat(entered, DirExists())


class TestArchitecture(TestCase):  # suppress(R0903)
    """Tests for psqtraviscontainer/architecture.py."""

    def test_unknown_architecture(self):
        """Check that creating a non-special architecture returns metadata."""
        check_methods = [
            architecture.Alias.universal,
            architecture.Alias.qemu,
            architecture.Alias.debian
        ]

        def function_returns_input(function):
            """Return true if function returns input."""
            return function("input") == "input"

        self.assertThat(check_methods,
                        AllMatch(MatchesPredicate(function_returns_input,
                                                  "% did not return same")))


class TestDistroLookup(TestCase):  # suppress(R0903)
    """Tests for looking up the distro."""

    def test_error_lookup_bad_distro(self):  # suppress(no-self-use)
        """Check that looking up a non-existent distro throws."""
        with ExpectedException(RuntimeError):
            distro.lookup({"distro": "noexist"})
