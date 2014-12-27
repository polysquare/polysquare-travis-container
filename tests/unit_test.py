# /tests/unit_test.py
#
# Unit tests for various utilities.
#
# Disable no-self-use in tests as all test methods must be
# instance methods and we don't necessarily have to use a matcher
# with them.
# pylint:  disable=no-self-use
#
# See LICENCE.md for Copyright information
"""Unit tests for various utilities."""

import os

from psqtraviscontainer import architecture
from psqtraviscontainer import directory
from psqtraviscontainer import distro

from testtools import ExpectedException
from testtools import TestCase

from testtools.matchers import AllMatch
from testtools.matchers import DirExists
from testtools.matchers import MatchesPredicate


class TestDirectoryNavigation(TestCase):

    """Tests for directory.py."""

    def test_enter_create_dir(self):
        """Check that we create a dir when entering a non-existent one."""
        does_not_exist = "does_not_exist"
        with directory.Navigation(os.path.join(os.getcwd(),
                                               does_not_exist)) as entered:
            self.assertThat(entered, DirExists())

    def test_enter_exist_dir(self):
        """Check that we can enter an existing dir."""
        existing_dir = os.path.join(os.getcwd(), "existing")
        os.makedirs(existing_dir)
        with directory.Navigation(existing_dir) as entered:
            self.assertThat(entered, DirExists())


class TestArchitecture(TestCase):

    """Tests for architecture.py."""

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


class TestDistroLookup(TestCase):

    """Tests for looking up the distro."""

    def test_error_lookup_bad_distro(self):
        """Check that looking up a non-existent distro throws."""
        with ExpectedException(RuntimeError):
            distro.lookup("noexist", "noexist", "noexist")
