# /psqtraviscontainer/container.py
#
# Abstract base class for an operating system container.
#
# See /LICENCE.md for Copyright information
"""Abstract base class for an operating system container."""

import abc

import os  # suppress(PYC50)

import re

import shutil

import subprocess

import sys

from collections import namedtuple

from contextlib import contextmanager

import parseshebang

import shutilwhich  # suppress(F401,PYC50,unused-import)

import six


@contextmanager
def updated_environ(prepend, overwrite):
    """Context with prepend added to and overwrite replacing os.environ."""
    env = os.environ.copy()
    for key, value in prepend.items():
        env[key] = "{0}{1}{2}".format(value,
                                      os.pathsep,
                                      env.get(key, ""))

    env.update(overwrite)

    old_environ = os.environ
    os.environ = env

    try:
        yield env
    finally:
        os.environ = old_environ


class AbstractContainer(six.with_metaclass(abc.ABCMeta, object)):
    """An abstract class representing an OS container."""

    PopenArguments = namedtuple("PopenArguments", "argv prepend overwrite")

    # vulture doesn't know that the __defaults__ attribute is actually
    # built-in.
    #
    # suppress(unused-attribute)
    PopenArguments.__new__.__defaults__ = (None, dict(), dict())

    @staticmethod
    def rmtree(directory):
        """Remove directory, but ignore errors."""
        try:
            shutil.rmtree(directory)
        except (shutil.Error, OSError):   # suppress(pointless-except)
            pass

    @abc.abstractmethod
    def _subprocess_popen_arguments(self, argv, **kwargs):
        """Return a PopenArguments tuple.

        This indicates what should be passed to subprocess.Popen when the
        execute method is called on this class.
        """
        del argv
        del kwargs

        raise NotImplementedError()

    @abc.abstractmethod
    def _package_system(self):
        """Return the package system this container should be using."""
        raise NotImplementedError()

    @abc.abstractmethod
    def clean(self):
        """Clean this container to prepare it for caching.

        Remove any non-useful files here.
        """
        raise NotImplementedError()

    def __enter__(self):
        """Use this container as a context."""
        return self

    def __exit__(self, exc_type, value, traceback):
        """Clean this container once it has been used a context."""
        del exc_type
        del value
        del traceback

        self.clean()

    def root_filesystem_directory(self):
        """Return absolute and real path to installed packages."""
        return os.path.realpath(self._root_filesystem_directory())

    def install_packages(self, repositories_path, packages_path):
        """Install packages and set up repositories as configured.

        :repositories_path: should be a path to a text file containing
                            a list of repositories to add to the package system
                            before installing any packages.
        :packages_path: should be a path to a text file containing a
                        list of packages to be installed.
        """
        if packages_path:
            package_system = self._package_system()

            # Add any repositories to the package system now
            if repositories_path:
                with open(repositories_path, "r") as repositories_file:
                    repo_lines = repositories_file.read().splitlines(False)

                package_system.add_repositories(repo_lines)

            with open(packages_path) as packages_file:
                packages = re.findall(r"[^\s]+", packages_file.read())

            package_system.install_packages(packages)

    def execute(self,
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **kwargs):
        """Execute the process and arguments indicated by argv in container."""
        (argv,
         prepend_env,
         overwrite_env) = self._subprocess_popen_arguments(argv, **kwargs)

        with updated_environ(prepend_env, overwrite_env) as env:
            if not os.path.exists(argv[0]):
                argv[0] = shutil.which(argv[0])
                assert argv[0] is not None

            # Also use which to find the shebang program - in some cases
            # we may only have the name of a program but not where it
            # actually exists. This is necessary on some platforms like
            # Windows where PATH is read from its state as it existed
            # when this process got created, not at the time Popen was
            # called.
            argv = parseshebang.parse(str(argv[0])) + argv
            if not os.path.exists(argv[0]):
                argv[0] = shutil.which(argv[0])
                assert argv[0] is not None

            executed_cmd = subprocess.Popen(argv,
                                            stdout=stdout,
                                            stderr=stderr,
                                            env=env,
                                            universal_newlines=True)

        stdout_data, stderr_data = executed_cmd.communicate()

        return (executed_cmd.returncode, stdout_data, stderr_data)

    def execute_success(self, argv, **kwargs):
        """Execute the command specified by argv, throws on failure."""
        returncode, stdout_data, stderr_data = self.execute(argv,
                                                            subprocess.PIPE,
                                                            subprocess.PIPE,
                                                            **kwargs)

        if returncode != 0:
            sys.stderr.write(stdout_data)
            sys.stderr.write(stderr_data)
            raise RuntimeError("""{0} failed with {1}""".format(" ".join(argv),
                                                                returncode))
