# /tests/create_test.py
#
# Test case for create.py, creating proot containers
#
# Disable no-self-use in tests as all test methods must be
# instance methods and we don't necessarily have to use a matcher
# with them.
# pylint:  disable=no-self-use
#
# See LICENCE.md for Copyright information
"""Test case for create.py, creating proot containers."""

import os

from psqtraviscontainer import create

import tempdir

from testtools import TestCase

from testtools.matchers import FileExists


def run_create_container_on_dir(directory, **kwargs):
    """Run main from create.py, setting the container to be at directory."""
    args = [directory]

    def _get_value_list(value):
        """Get representation of value as a list."""
        if isinstance(value, list):
            return value
        else:
            return [repr(value)]

    for key, value in kwargs:
        args.append("--{0}".format(key))
        args.append(_get_value_list(value))

    create.main(arguments=args)


def run_create_container(**kwargs):
    """Run main() from create.py and returns the container TempDir.

    This houses the container created. Keyword args are converted
    into switch arguments as appropriate.
    """
    temp_dir = tempdir.TempDir()
    run_create_container_on_dir(temp_dir.name, **kwargs)
    return temp_dir


class ContainerInspectionTestCase(TestCase):

    """TestCase where container persists until all tests have completed.

    No modifications should be made to the container during any
    individual test. The order of tests should not be relied upon.
    """

    container_temp_dir = None

    @classmethod
    def create_container_for_test(cls, **kwargs):
        """Overridable method to create a container for this test case."""
        cls.container_temp_dir = run_create_container(**kwargs)

    # Suppress flake8 complaints about uppercase characters in function names,
    # these functions are overloaded
    @classmethod
    def setUpClass(cls):  # NOQA
        """Set up container for all tests in this test case."""
        cls.create_container_for_test()

    @classmethod
    def tearDownClass(cls):  # NOQA
        """Dissolve container for all tests in this test case."""
        cls.container_temp_dir.dissolve()
        cls.container_temp_dir = None


_PROOT_DISTRO_STAMP = ".have-proot-distribution"


class TestCreateProot(TestCase):

    """A test case for proot creation basics."""

    def test_create_proot_distro(self):
        """Check that we create a proot distro."""
        with run_create_container() as container:
            self.assertThat(os.path.join(container, _PROOT_DISTRO_STAMP),
                            FileExists())

    def test_use_existing_proot_distro(self):
        """Check that we re-use an existing proot distro.

        In that case, the timestamp for .have-proot-distribution and
        make sure that across two runs they are actual. If they were,
        then no re-downloading took place.
        """
        with run_create_container() as container:
            path_to_proot_stamp = os.path.join(container,
                                               _PROOT_DISTRO_STAMP)

            first_timestamp = os.stat(path_to_proot_stamp).st_mtime

            run_create_container_on_dir(container)

            second_timestamp = os.stat(path_to_proot_stamp).st_mtime

            self.assertEqual(first_timestamp, second_timestamp)
