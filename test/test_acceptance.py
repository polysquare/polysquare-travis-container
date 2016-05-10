# /test/test_acceptance.py
#
# Test case for psqtraviscontainer/create.py, creating proot containers
#
# See /LICENCE.md for Copyright information
"""Test case for psqtraviscontainer/create.py, creating proot containers."""

import os

import platform

import stat

import sys

import tempfile

from collections import namedtuple

from contextlib import contextmanager

from test.testutil import (download_file_cached,
                           temporary_environment)

from nose_parameterized import parameterized

from psqtraviscontainer import architecture
from psqtraviscontainer import create
from psqtraviscontainer import use

from psqtraviscontainer.architecture import Alias

from psqtraviscontainer.constants import have_proot_distribution
from psqtraviscontainer.constants import proot_distribution_dir

from psqtraviscontainer.distro import available_distributions

from psqtraviscontainer.linux_container import get_dir_for_distro

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
        except (IOError, OSError):  # suppress(pointless-except)
            # IOError and OSError are fine. The directory will be deleted by
            # the user's operating system a little later, there's not much we
            # can do about this.
            pass

    @property
    def name(self):
        """Getter for 'name'."""
        return self._temp_dir.name


def run_create_container_on_dir(directory, *args, **kwargs):
    """Run main setting the container to be at directory."""
    del args

    arguments = [directory] + _convert_to_switch_args(kwargs)

    with cached_downloads():
        create.main(arguments=arguments)


def run_create_container(**kwargs):
    """Run main() and returns the container in a TempDir.

    This houses the container created. Keyword args are converted
    into switch arguments as appropriate.
    """
    temp_dir = SafeTempDir()
    run_create_container_on_dir(temp_dir.name, **kwargs)
    return temp_dir


def default_create_container_arguments():
    """Get set of arguments which would create first known distribution."""
    distro_config = list(available_distributions())[0]
    arguments = ("distro", "release")
    config = {k: v for k, v in distro_config.items() if k in arguments}
    return config


def run_create_default_container():
    """Run main() and return container for first known distribution."""
    return run_create_container(**(default_create_container_arguments()))


def run_use_container_on_dir(directory, **kwargs):
    """Run main() from psqtraviscontainer/use.py and return status code."""
    cmd = kwargs["cmd"]
    del kwargs["cmd"]

    arguments = [directory] + _convert_to_switch_args(kwargs) + ["--"] + cmd

    return use.main(arguments=arguments)


def test_case_requiring_platform(system):
    """Get a TestCase base class which can only be run on platform."""
    class TestCaseRequiring(TestCase):
        """A wrapper around TestCase which only runs tests on platform."""

        def setUp(self):  # suppress(N802)
            """Automatically skips tests if not run on platform."""
            super(TestCaseRequiring, self).setUp()
            if platform.system() != system:
                self.skipTest("""not running on system - {0}""".format(system))

    return TestCaseRequiring


class TestCreateProot(test_case_requiring_platform("Linux")):
    """A test case for proot creation basics."""

    def test_create_proot_distro(self):
        """Check that we create a proot distro."""
        with run_create_default_container() as container:
            self.assertThat(have_proot_distribution(container),
                            FileExists())

    def test_use_existing_proot_distro(self):
        """Check that we re-use an existing proot distro.

        In that case, the timestamp for /.have-proot-distribution and
        make sure that across two runs they are actual. If they were,
        then no re-downloading took place.
        """
        with run_create_default_container() as container:
            path_to_proot_stamp = have_proot_distribution(container)

            first_timestamp = os.stat(path_to_proot_stamp).st_mtime

            config = default_create_container_arguments()
            run_create_container_on_dir(container, **config)

            second_timestamp = os.stat(path_to_proot_stamp).st_mtime

            self.assertEqual(first_timestamp, second_timestamp)


@contextmanager
def cached_downloads():
    """Context manager to ensure that download_file is patched to use cache."""
    import six
    import psqtraviscontainer.download  # suppress(PYC50)

    original_download_file = psqtraviscontainer.download.download_file
    psqtraviscontainer.download.download_file = download_file_cached

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    if not os.environ.get("_POLYSQUARE_TRAVIS_CONTAINER_TEST_SHOW_OUTPUT",
                          None):
        sys.stdout = six.StringIO()
        sys.stderr = six.StringIO()

    try:
        yield
    finally:
        psqtraviscontainer.download.download_file = original_download_file
        sys.stdout = original_stdout
        sys.stderr = original_stderr


class ContainerInspectionTestCase(TestCase):
    """TestCase where container persists until all tests have completed.

    No modifications should be made to the container during any
    individual test. The order of tests should not be relied upon.
    """

    container_temp_dir = None

    def __init__(self, *args, **kwargs):
        """Initialize class."""
        cls = ContainerInspectionTestCase
        super(cls, self).__init__(*args, **kwargs)
        self.container_dir = None

    def setUp(self):  # suppress(N802)
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
    def setUpClass(cls):  # suppress(N802)
        """Set up container for all tests in this test case."""
        with temporary_environment(_FORCE_DOWNLOAD_QEMU="True"):
            config = default_create_container_arguments()
            cls.create_container(**config)

    @classmethod
    def tearDownClass(cls):  # suppress(N802)
        """Dissolve container for all tests in this test case."""
        if cls.container_temp_dir:
            cls.container_temp_dir.dissolve()
            cls.container_temp_dir = None


QEMU_ARCHITECTURES = [
    "arm",
    "i386",
    "ppc",
    "x86_64"
]


def _format_arch(func, num, params):
    """Format docstring for TestProotDistribution parameterized tests."""
    del num

    return func.__doc__.format(arch=params[0][0])


class TestProotDistribution(ContainerInspectionTestCase):
    """Tests to inspect a proot distribution itself."""

    def setUp(self):   # suppress(N802)
        """Set up TestProotDistribution."""
        if platform.system() != "Linux":
            self.skipTest("""proot is only available on linux""")

        super(TestProotDistribution, self).setUp()

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

    @parameterized.expand(QEMU_ARCHITECTURES, testcase_func_doc=_format_arch)
    def test_has_qemu_executables(self, arch):
        """Check that we have a qemu executable qemu-{arch}."""
        cont = proot_distribution_dir(self.container_dir)
        self.assertThat(os.path.join(cont, "bin/qemu-{}".format(arch)),
                        FileExists())

    @parameterized.expand(QEMU_ARCHITECTURES, testcase_func_doc=_format_arch)
    def test_qemu_binary_is_executable(self, arch):
        """Check that qemu binary qemu-{arch} is executable."""
        cont = proot_distribution_dir(self.container_dir)
        proot_binary = os.path.join(cont, "bin/qemu-{}".format(arch))
        stat_result = os.stat(proot_binary)
        executable_mask = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        self.assertTrue(stat_result.st_mode & executable_mask != 0)


def exec_for_returncode(*argv):
    """Execute command for its return code.

    Check that use.main() returns exit code of subprocess.
    """
    config = default_create_container_arguments()
    with run_create_container(**config) as cont:
        use_config = config.copy()
        use_config["cmd"] = list(argv)
        return run_use_container_on_dir(cont,
                                        **use_config)


PLATFORM_PROGRAM_MAPPINGS = {
    "Linux": {
        "0": ["true"],
        "1": ["false"]
    },
    "Darwin": {
        "0": ["true"],
        "1": ["false"]
    },
    "Windows": {
        "0": ["python", "-c", "import sys;sys.exit(0);"],
        "1": ["python", "-c", "import sys;sys.exit(1);"]
    }
}


class TestExecInContainer(TestCase):
    """A test case for executing things inside a container."""

    def test_exec_fail_no_distro(self):  # suppress(no-self-use)
        """Check that use.main() fails where there is no distro."""
        with run_create_default_container() as container_dir:
            with ExpectedException(RuntimeError):
                cmd = PLATFORM_PROGRAM_MAPPINGS[platform.system()]["0"]
                run_use_container_on_dir(container_dir, cmd=cmd)

    def test_exec_return_zero(self):
        """Check that use.main() returns true exit code of subprocess."""
        cmd = PLATFORM_PROGRAM_MAPPINGS[platform.system()]["0"]
        self.assertEqual(exec_for_returncode(*cmd), 0)

    def test_exec_return_one(self):
        """Check that use.main() returns false exit code of subprocess."""
        cmd = PLATFORM_PROGRAM_MAPPINGS[platform.system()]["1"]
        self.assertEqual(exec_for_returncode(*cmd), 1)

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
        """Use as context manager."""
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
                        repos,
                        packages,
                        test_files,
                        **kwargs):
    """Create a TemplateDistroTest class."""
    class TemplateDistroTest(ContainerInspectionTestCase):
        """Template for checking a distro proot."""

        def __init__(self, *args, **kwargs):
            """Initialize members used by this class."""
            cls = TemplateDistroTest
            super(cls, self).__init__(*args, **kwargs)
            self.path_to_distro_root = None

        def setUp(self):  # suppress(N802)
            """Set up path to distro root."""
            super(TemplateDistroTest, self).setUp()

        @classmethod
        def setUpClass(cls):  # suppress(N802)
            """Create a container for all uses of this TemplateDistroTest."""
            with InstallationConfig(packages, repos) as command_config:
                keys = ("distro", "release")
                kwargs.update({k: v for k, v in config.items() if k in keys})

                cls.create_container(repos=command_config.repos_path,
                                     packages=command_config.packages_path,
                                     **kwargs)

        def test_distro_folder_exists(self):
            """Check that distro folder exists for ."""
            if platform.system() == "Linux":
                root = get_dir_for_distro(self.container_dir,
                                          config)
                self.assertThat(os.path.join(self.container_dir, root),
                                DirExists())
            elif platform.system() == "Darwin":
                self.assertThat(os.path.join(self.container_dir, "bin"),
                                DirExists())

        def test_has_package_installed(self):
            """Check that our testing package got installed.

            If it did get installed, then it means that the repository
            was successfully added and the package was successfully installed
            using the native tool. That means that the proot "works".
            """
            format_kwargs = dict()

            if kwargs.get("release", None) == "trusty":
                self.skipTest("""Trusty images are currently unavailable""")
                return

            if platform.system() == "Linux":
                root = get_dir_for_distro(self.container_dir,
                                          config)
                distro_arch = architecture.Alias.debian(kwargs["arch"])
                archlib = ARCHITECTURE_LIBDIR_MAPPINGS[distro_arch]
                format_kwargs["archlib"] = archlib
            else:
                root = self.container_dir

            # Match against a list of files. If none of the results are None,
            # then throw a list of mismatches.
            match_results = []
            for filename in test_files:
                path_to_file = os.path.join(root,
                                            filename.format(**format_kwargs))
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
                                    "lib64/libaio.so.1.0.1"]),
    "OSX": _DistroPackage(package="xz",
                          repo=[],
                          files=["bin/xz"]),
    "Windows": _DistroPackage(package="cmake.portable",
                              repo=[],
                              files=["lib/cmake.portable.3.5.2/"
                                     "tools/cmake-3.5.2-win32-x86/bin/"
                                     "cmake.exe"])
}


def get_distribution_tests():
    """Fetch distribution tests as dictionary."""
    tests = {}

    for config in available_distributions():
        config = config.copy()
        name_array = bytearray()
        for key in sorted(list(config.keys())):
            if key in ("info", "pkgsys", "url"):
                continue

            name_array += bytes(key[0].upper().encode() +
                                key[1:].encode() +
                                config[key][0].upper().encode() +
                                config[key][1:].encode())
        name = "Test{0}".format(name_array.decode("ascii"))

        distro = config["distro"]
        repositories_to_add = _DISTRO_INFO[distro].repo
        packages_to_install = [_DISTRO_INFO[distro].package]
        files_to_test_for = _DISTRO_INFO[distro].files
        kwargs = dict()

        try:
            kwargs["arch"] = Alias.universal(config["arch"])
        except KeyError:  # suppress(pointless-except)
            pass

        tests[name] = _create_distro_test(name,
                                          config,
                                          repositories_to_add,
                                          packages_to_install,
                                          files_to_test_for,
                                          **kwargs)

    return tests

for _name, _test in get_distribution_tests().items():
    exec("{0} = _test".format(_name))  # pylint:disable=W0122
    del _test
