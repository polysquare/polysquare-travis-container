# /tests/acceptance_test.py
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

import gc

import os

import platform

import stat

import tempfile

from collections import namedtuple

from nose_parameterized import parameterized

from psqtraviscontainer import architecture
from psqtraviscontainer import create
from psqtraviscontainer import distro
from psqtraviscontainer import use

from psqtraviscontainer.architecture import Alias

from psqtraviscontainer.constants import have_proot_distribution
from psqtraviscontainer.constants import proot_distribution_dir

from psqtraviscontainer.distro import AVAILABLE_DISTRIBUTIONS

import tempdir

from testtools import ExpectedException
from testtools import TestCase

from testtools.matchers import DirExists
from testtools.matchers import FileExists


def _convert_to_switch_args(kwargs):
    """Convert keyword arguments to command line switches."""
    arguments = []

    def _get_representation(value):
        """Get representation of value as a list."""
        if isinstance(value, list):
            return " ".join(value)
        else:
            return str(value)

    for key, value in kwargs.items():
        arguments.append("--{0}".format(key))
        arguments.append(_get_representation(value))

    return arguments


class SafeTempDir(object):  # pylint:disable=R0903

    """A TempDir that dissolves on __exit__, ignoring PermissionError."""

    def __init__(self):
        """Forward initialization."""
        super(SafeTempDir, self).__init__()
        self._temp_dir = tempdir.TempDir()

    def __enter__(self):
        """Return internal tempdir."""
        return self._temp_dir.__enter__()

    def __exit__(self, exc_type, value, traceback):
        """Call dissolve."""
        del exc_type
        del value
        del traceback

        self.dissolve()

    def dissolve(self):
        """Forward to TempDir dissolve function, ignore PermissionError."""
        try:
            self._temp_dir.dissolve()
        except (IOError, OSError):  # pylint:disable=W0704
            # IOError and OSError are fine. The directory will be deleted by
            # the user's operating system a little later, there's not much we
            # can do about this.
            pass

    @property
    def name(self):
        """Getter for 'name'."""
        return self._temp_dir.name


def run_create_container_on_dir(directory, *args, **kwargs):
    """Run main from create.py, setting the container to be at directory."""
    del args

    arguments = [directory] + _convert_to_switch_args(kwargs)

    create.main(arguments=arguments)

    # Run the garbage collector so that open files from argparse.ArgumentParser
    # in main() get closed.
    gc.collect()


def run_create_container(**kwargs):
    """Run main() from create.py and returns the container TempDir.

    This houses the container created. Keyword args are converted
    into switch arguments as appropriate.
    """
    temp_dir = SafeTempDir()
    run_create_container_on_dir(temp_dir.name, **kwargs)
    return temp_dir


def run_use_container_on_dir(directory, **kwargs):
    """Run main() from use.py and return status code."""
    arguments = [directory] + _convert_to_switch_args(kwargs)

    return use.main(arguments=arguments)


class TestCreateProot(TestCase):

    """A test case for proot creation basics."""

    def test_create_proot_distro(self):
        """Check that we create a proot distro."""
        with run_create_container() as container:
            self.assertThat(have_proot_distribution(container),
                            FileExists())

    def test_use_existing_proot_distro(self):
        """Check that we re-use an existing proot distro.

        In that case, the timestamp for .have-proot-distribution and
        make sure that across two runs they are actual. If they were,
        then no re-downloading took place.
        """
        with run_create_container() as container:
            path_to_proot_stamp = have_proot_distribution(container)

            first_timestamp = os.stat(path_to_proot_stamp).st_mtime

            run_create_container_on_dir(container)

            second_timestamp = os.stat(path_to_proot_stamp).st_mtime

            self.assertEqual(first_timestamp, second_timestamp)


class ContainerInspectionTestCase(TestCase):

    """TestCase where container persists until all tests have completed.

    No modifications should be made to the container during any
    individual test. The order of tests should not be relied upon.
    """

    container_temp_dir = None

    def __init__(self, *args, **kwargs):
        """Initialize class."""
        cls = ContainerInspectionTestCase
        super(cls, self).__init__(*args, **kwargs)  # pylint:disable=W0142
        self.container_dir = None

    def setUp(self):  # NOQA
        """Set up container dir."""
        super(ContainerInspectionTestCase, self).setUp()
        self.container_dir = self.__class__.container_temp_dir.name

    @classmethod
    def create_container(cls, **kwargs):
        """Overridable method to create a container for this test case."""
        cls.container_temp_dir = run_create_container(**kwargs)

    # Suppress flake8 complaints about uppercase characters in function names,
    # these functions are overloaded
    @classmethod
    def setUpClass(cls):  # NOQA
        """Set up container for all tests in this test case."""
        cls.create_container()

    @classmethod
    def tearDownClass(cls):  # NOQA
        """Dissolve container for all tests in this test case."""
        try:
            cls.container_temp_dir.dissolve()
        except IOError:  # pylint:disable=W0704
            # IOError is fine. The directory will be deleted by the
            # user's operating system a little later, there's not much we
            # can do about this.
            pass
        cls.container_temp_dir = None


QEMU_ARCHITECTURES = [
    "arm",
    "armeb",
    "i386",
    "ppc",
    "x86_64"
]


class TestProotDistribution(ContainerInspectionTestCase):

    """Tests to inspect a proot distribution itself."""

    def test_has_proot_dir(self):
        """Check that we have a proot directory in our distribution."""
        self.assertThat(proot_distribution_dir(self.container_dir),
                        DirExists())

    def test_has_proot_executable(self):
        """Check that we have a proot executable in our distribution."""
        cont = proot_distribution_dir(self.container_dir)
        self.assertThat(os.path.join(cont, "bin/proot"),
                        FileExists())

    def test_proot_binary_is_executable(self):
        """Check that that the proot binary is executable."""
        cont = proot_distribution_dir(self.container_dir)
        proot_binary = os.path.join(cont, "bin/proot")
        stat_result = os.stat(proot_binary)
        executable_mask = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        self.assertTrue(stat_result.st_mode & executable_mask != 0)

    @parameterized.expand(QEMU_ARCHITECTURES)
    def test_has_qemu_executables(self, arch):
        """Check that we have a qemu executable {0}.""".format("qemu-" + arch)
        cont = proot_distribution_dir(self.container_dir)
        self.assertThat(os.path.join(cont, "bin/qemu-{0}".format(arch)),
                        FileExists())

    @parameterized.expand(QEMU_ARCHITECTURES)
    def test_qemu_binary_is_executable(self, arch):
        """Check that qemu binary {0} is executable.""".format("qemu-" + arch)
        cont = proot_distribution_dir(self.container_dir)
        proot_binary = os.path.join(cont, "bin/qemu-{0}".format(arch))
        stat_result = os.stat(proot_binary)
        executable_mask = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        self.assertTrue(stat_result.st_mode & executable_mask != 0)


class TestExecInContainer(TestCase):

    """A test case for executing things insie a container."""

    def test_exec_fail_no_distro(self):
        """Check that use.main() fails where there is no distro."""
        with run_create_container() as container_dir:
            with ExpectedException(RuntimeError):
                distro_config = AVAILABLE_DISTRIBUTIONS[0]
                run_use_container_on_dir(container_dir,
                                         distro=distro_config.type,
                                         release=distro_config.release,
                                         cmd="true")

    def _exec_for_returncode(self, cmd):
        """Execute command for its return code.

        Check that use.main() returns exit code of subprocess.
        """
        distro_config = AVAILABLE_DISTRIBUTIONS[0]
        config = {
            "distro": distro_config.type,
            "release": distro_config.release
        }

        with run_create_container(**config) as cont:  # pylint:disable=W0142
            kwargs = config
            kwargs["cmd"] = cmd
            return run_use_container_on_dir(cont,  # pylint:disable=W0142
                                            **kwargs)

    def test_exec_return_zero(self):
        """Check that use.main() returns true exit code of subprocess."""
        self.assertEqual(self._exec_for_returncode("true"), 0)

    def test_exec_return_one(self):
        """Check that use.main() returns false exit code of subprocess."""
        self.assertEqual(self._exec_for_returncode("false"), 1)

ARCHITECTURE_LIBDIR_MAPPINGS = {
    "armhf": "arm-linux-gnueabihf",
    "i386": "i386-linux-gnu",
    "amd64": "x86_64-linux-gnu",
    "arm64": "arm64-linux-gnu",
    "powerpc": "powerpc-linux-gnu",
    "ppc64el": "ppc64el-linux-gnu"
}


class InstallationConfig(object):  # pylint:disable=R0903

    """Manages configuration files."""

    def __init__(self, packages, repos):
        """Create temporary files for packages and repos."""
        packages_fd, self.packages_path = tempfile.mkstemp()
        repos_fd, self.repos_path = tempfile.mkstemp()

        packages_file = os.fdopen(packages_fd, "a")
        repos_file = os.fdopen(repos_fd, "a")

        for package in packages:
            packages_file.write("{0}\n".format(package))

        for repository in repos:
            repos_file.write("{0}\n".format(repository))

        packages_file.close()
        repos_file.close()

    def __enter__(self):
        """Use as ContextManager."""
        return self

    def __exit__(self, exc_type, value, traceback):
        """Destroy temporary files."""
        del exc_type
        del value
        del traceback

        os.remove(self.packages_path)
        os.remove(self.repos_path)


def _create_distro_test(test_name,  # pylint:disable=R0913
                        config,
                        arch,
                        repos,
                        packages,
                        test_files):
    """Create a TestDistribution class."""
    class TemplateDistroTest(ContainerInspectionTestCase):

        """Template for checking a distro proot."""

        def __init__(self, *args, **kwargs):
            """Initialize members used by this class."""
            cls = TemplateDistroTest
            super(cls, self).__init__(*args, **kwargs)  # pylint:disable=W0142
            self.path_to_distro_root = None

        def setUp(self):  # NOQA
            """Set up path to distro root."""
            super(TemplateDistroTest, self).setUp()
            root = distro.get_dir(self.container_dir,
                                  config,
                                  config.archfetch(arch))
            self.path_to_distro_root = os.path.join(self.container_dir, root)

        @classmethod
        def setUpClass(cls):  # NOQA
            """Create a container for all uses of this TemplateDistroTest."""
            with InstallationConfig(packages, repos) as command_config:
                cls.create_container(distro=config.type,
                                     release=config.release,
                                     arch=arch,
                                     repos=command_config.repos_path,
                                     packages=command_config.packages_path)

        def test_distro_folder_exists(self):
            """Check that distro folder exists for ."""
            self.assertThat(self.path_to_distro_root, DirExists())

        def test_has_package_installed(self):
            """Check that our testing package got installed.

            If it did get installed, then it means that the repository
            was successfully added and the package was successfully installed
            using the native tool. That means that the proot "works".
            """
            distro_arch = architecture.Alias.debian(arch)
            archlib = ARCHITECTURE_LIBDIR_MAPPINGS[distro_arch]

            # Match against a list of files. If none of the results are None,
            # then throw a list of mismatches.
            match_results = []
            for filename in test_files:
                path_to_file = os.path.join(self.path_to_distro_root,
                                            filename.format(archlib=archlib))
                result = FileExists().match(path_to_file)
                if result:
                    match_results.append(result)

            if len(match_results) == len(test_files):
                raise Exception(repr(match_results))

    TemplateDistroTest.__name__ = test_name
    return TemplateDistroTest

_DistroPackage = namedtuple("_DistroPackage", "package files repo")
_DISTRO_INFO = {
    "Ubuntu": _DistroPackage(package="libaacs0",
                             repo=["{ubuntu} {release} universe"],
                             files=["usr/lib/{archlib}/libaacs.so.0"]),
    "Debian": _DistroPackage(package="libaio1",
                             repo=[],
                             files=["lib/libaio.so.1.0.1",
                                    "lib/{archlib}/libaio.so.1.0.1"]),
    "Fedora": _DistroPackage(package="libaio",
                             repo=[],
                             files=["lib/libaio.so.1.0.1",
                                    "lib64/libaio.so.1.0.1"])
}


def _blacklisted_arch():
    """Return universal formatted blacklisted arch for current arch."""
    blacklist = {
        "x86": "x86_64",
        "x86_64": "x86"
    }

    try:
        return blacklist[Alias.universal(platform.machine())]
    except KeyError:
        return None


def get_distribution_tests():
    """Fetch distribution tests as dictionary."""
    tests = {}

    for config in AVAILABLE_DISTRIBUTIONS:
        for distro_arch in config.archs:
            # Blacklist 64-bit ABIs that don't emulate properly
            if Alias.universal(distro_arch) != _blacklisted_arch():
                name = "Test{0}{1}{2}Distro".format(config.type,
                                                    config.release,
                                                    distro_arch)

                repositories_to_add = _DISTRO_INFO[config.type].repo
                packages_to_install = [_DISTRO_INFO[config.type].package]
                files_to_test_for = _DISTRO_INFO[config.type].files
                tests[name] = _create_distro_test(name,
                                                  config,
                                                  Alias.universal(distro_arch),
                                                  repositories_to_add,
                                                  packages_to_install,
                                                  files_to_test_for)

    return tests

for _name, _test in get_distribution_tests().items():
    exec("{0} = _test".format(_name))  # pylint:disable=W0122
    del _test
