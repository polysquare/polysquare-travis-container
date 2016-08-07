# /psqtraviscontainer/package_system.py
#
# Implementations of package-system controllers for various distributions.
#
# See /LICENCE.md for Copyright information
"""Implementations of package-system controllers for various distributions."""

import abc

import errno

import fnmatch

import os

import platform

import shutil

import subprocess

import sys

import tarfile

import tempfile

import textwrap

from collections import namedtuple

from clint.textui import colored

from psqtraviscontainer import directory
from psqtraviscontainer import download

import six

import tempdir

_UBUNTU_MAIN_ARCHS = ["i386", "amd64"]
_UBUNTU_PORT_ARCHS = ["armhf", "arm64", "powerpc", "ppc64el"]
_UBUNTU_MAIN_ARCHIVE = "http://archive.ubuntu.com/ubuntu/"
_UBUNTU_PORT_ARCHIVE = "http://ports.ubuntu.com/ubuntu-ports/"


def _report_task(description):
    """Report task description."""
    sys.stdout.write(str(colored.white("-> {0}\n".format(description))))


def _run_task(executor, description, argv, env=None, detail=None):
    """Run command through executor argv and prints description."""
    def wrapper(line):
        """Output wrapper for line."""
        return textwrap.indent(line, "   ")

    detail = "[{}]".format(" ".join(argv)) if detail is None else detail
    _report_task(description + " " + detail)
    (code,
     stdout_data,
     stderr_data) = executor.execute(argv,
                                     output_modifier=wrapper,
                                     live_output=True,
                                     requires_full_access=True,
                                     env=env)
    sys.stderr.write(stderr_data)


def _format_package_list(packages):
    """Return a nicely formatted list of package names."""
    "\n   (*) ".join([""] + packages)


class PackageSystem(six.with_metaclass(abc.ABCMeta, object)):
    """An abstract class representing a package manager."""

    PopenArguments = namedtuple("PopenArguments", "argv env")

    @abc.abstractmethod
    def add_repositories(self, repos):
        """Add repositories to central packaging system."""
        del repos

        raise NotImplementedError()

    @abc.abstractmethod
    def install_packages(self, package_names):
        """Install specified packages in package_names."""
        del package_names

        raise NotImplementedError()


class Dpkg(PackageSystem):
    """Debian Packaging System."""

    def __init__(self,
                 release,
                 arch,
                 executor):
        """Initialize Dpkg with release and arch."""
        super(Dpkg, self).__init__()
        self._release = release
        self._arch = arch
        self._executor = executor

    @staticmethod
    def format_repositories(repos, release, arch):
        """Take a list of APT lines and format them.

        There are certain shortcuts that you can use.

        {ubuntu} will be replaced by http://archive.ubuntu.com/ and
        the architecture.

        {debian} will be replaced by http://ftp.debian.org/.

        {launchpad} will be replaced by "http://ppa.launchpad.net/.

        {release} gets replaced by the release of the distribution, which
        means you don't need a repository file for every distribution.
        """
        _ubuntu_urls = [
            (_UBUNTU_MAIN_ARCHS, _UBUNTU_MAIN_ARCHIVE),
            (_UBUNTU_PORT_ARCHS, _UBUNTU_PORT_ARCHIVE)
        ]

        def _format_user_line(line, kwargs):
            """Format a line and turns it into a valid repository line."""
            formatted_line = line.format(**kwargs)
            return "deb {0}".format(formatted_line)

        def _value_or_error(value):
            """Return first item in value, or ERROR if value is empty."""
            return value[0] if len(value) else "ERROR"

        format_keys = {
            "ubuntu": [u[1] for u in _ubuntu_urls if arch in u[0]],
            "debian": ["http://ftp.debian.org/"],
            "launchpad": ["http://ppa.launchpad.net/"],
            "release": [release]
        }
        format_keys = {
            k: _value_or_error(v) for k, v in format_keys.items()
        }

        return [_format_user_line(l, format_keys) for l in repos]

    def add_repositories(self, repos):
        """Add a repository to the central packaging system."""
        # We will be creating a bash script each time we need to add
        # a new source line to our sources list and executing that inside
        # the proot. This guarantees that we'll always get the right
        # permissions.
        with tempfile.NamedTemporaryFile() as bash_script:
            append_lines = Dpkg.format_repositories(repos,
                                                    self._release,
                                                    self._arch)
            for count, append_line in enumerate(append_lines):
                path = "/etc/apt/sources.list.d/{0}.list".format(count)
                append_cmd = "echo \"{0}\" > {1}\n".format(append_line, path)
                bash_script.write(six.b(append_cmd))

            bash_script.flush()
            self._executor.execute_success(["bash", bash_script.name],
                                           requires_full_access=True)

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        if len(package_names):
            _run_task(self._executor,
                      """Update repositories""",
                      ["apt-get", "update", "-y", "--force-yes"])
            _run_task(self._executor,
                      """Install APT packages""",
                      ["apt-get",
                       "install",
                       "-y",
                       "--force-yes"] + package_names,
                      detail=_format_package_list(package_names))


class DpkgLocal(PackageSystem):
    """Debian packaging system, installing packages to local directory."""

    def __init__(self, release, arch, executor):
        """Initialize this PackageSystem."""
        super(DpkgLocal, self).__init__()
        self._release = release
        self._arch = arch
        self._executor = executor

    def _initialize_directories(self):
        """Ensure that all APT and Dpkg directories are initialized."""
        root = self._executor.root_filesystem_directory()
        directory.safe_makedirs(os.path.join(root,
                                             "var",
                                             "cache",
                                             "apt",
                                             "archives",
                                             "partial"))
        directory.safe_makedirs(os.path.join(root,
                                             "var",
                                             "lib",
                                             "apt",
                                             "lists",
                                             "partial"))
        directory.safe_makedirs(os.path.join(root,
                                             "var",
                                             "lib",
                                             "dpkg",
                                             "updates"))
        directory.safe_makedirs(os.path.join(root,
                                             "var",
                                             "lib",
                                             "dpkg",
                                             "info"))
        directory.safe_makedirs(os.path.join(root,
                                             "var",
                                             "lib",
                                             "dpkg",
                                             "parts"))
        directory.safe_touch(os.path.join(root,
                                          "var",
                                          "lib",
                                          "dpkg",
                                          "status"))
        directory.safe_touch(os.path.join(root,
                                          "var",
                                          "lib",
                                          "dpkg",
                                          "available"))

        for confpath in ["apt.conf",
                         "preferences",
                         "trusted.gpg",
                         "sources.list"]:
            directory.safe_makedirs(os.path.join(root,
                                                 "etc",
                                                 "apt",
                                                 confpath + ".d"))

        config_file_contents = "\n".join([
            "Apt {",
            "    Architecture \"" + self._arch + "\";",
            "    Get {",
            "        Assume-Yes true;",
            "    };",
            "};",
            "debug {",
            "    nolocking true;"
            "};"
            "Acquire::Queue-Mode \"host\";",
            "Dir \"" + root + "\";",
            "Dir::Cache \"" + root + "/var/cache/apt\";",
            "Dir::State \"" + root + "/var/lib/apt\";"
        ])
        with open(os.path.join(root, "etc", "apt.conf"), "w") as config_file:
            config_file.write(config_file_contents)

    def add_repositories(self, repos):
        """Add repository to the central packaging system."""
        self._initialize_directories()

        root = self._executor.root_filesystem_directory()
        sources_list = os.path.join(root, "etc", "apt", "sources.list")

        try:
            with open(sources_list) as sources:
                known_repos = [s for s in sources.read().split("\n") if len(s)]
        except EnvironmentError as error:
            if error.errno != errno.ENOENT:
                raise error

            known_repos = []

        all_repos = (set(Dpkg.format_repositories(repos,
                                                  self._release,
                                                  self._arch)) |
                     set(known_repos))

        with open(sources_list, "w") as sources:
            sources.write("\n".join(sorted(list(all_repos))))

    def install_packages(self, package_names):
        """Install all packages in list package_names.

        This works in a somewhat non-standard way. We will be
        updating the repository list as usual, but will be
        using a combination of apt-get download and
        dpkg manually to install packages into a local
        directory which we control.
        """
        self._initialize_directories()

        from six.moves.urllib.parse import urlparse  # suppress(import-error)

        root = self._executor.root_filesystem_directory()
        environment = {
            "APT_CONFIG": os.path.join(root, "etc", "apt.conf")
        }
        _run_task(self._executor,
                  """Update repositories""",
                  ["apt-get", "update", "-y", "--force-yes"],
                  env=environment)

        # Separate out into packages that need to be downloaded with
        # apt-get and packages that can be downloaded directly
        # using download_file
        deb_packages = [p for p in package_names if urlparse(p).scheme]
        apt_packages = [p for p in package_names if not urlparse(p).scheme]

        # Clear out /var/cache/apt/archives
        archives = os.path.join(root, "var", "cache", "apt", "archives")
        if os.path.exists(archives):
            shutil.rmtree(archives)
            os.makedirs(archives)

        if len(deb_packages):
            with directory.Navigation(archives):
                _report_task("""Downloading user-specified packages""")
                for deb in deb_packages:
                    download.download_file(deb)

        # Now use apt-get install -d to download the apt_packages and their
        # dependencies, but not install them
        if len(apt_packages):
            _run_task(self._executor,
                      """Downloading APT packages and dependencies""",
                      ["apt-get",
                       "-y",
                       "--force-yes",
                       "-d",
                       "install",
                       "--reinstall"] + apt_packages,
                      env=environment,
                      detail=_format_package_list(apt_packages))

        # Go back into our archives directory and unpack all our packages
        with directory.Navigation(archives):
            package_files = fnmatch.filter(os.listdir("."), "*.deb")
            for pkg in package_files:
                _run_task(self._executor,
                          """Unpacking """,
                          ["dpkg", "-x", pkg, root],
                          detail=os.path.splitext(os.path.basename(pkg))[0])


class Yum(PackageSystem):
    """Red Hat Packaging System."""

    def __init__(self,
                 release,
                 arch,
                 executor):
        """Initialize Yum with release and executor."""
        del arch
        del release

        super(Yum, self).__init__()
        self._executor = executor

    def add_repositories(self, repos):
        """Add a repository to the central packaging system."""
        with tempdir.TempDir() as download_dir:
            with directory.Navigation(download_dir):
                for repo in repos:
                    repo_file = download.download_file(repo)
                    # Create a bash script to copy the downloaded repo file
                    # over to /etc/yum/repos.d
                    with tempfile.NamedTemporaryFile() as bash_script:
                        copy_cmd = ("cp \"{0}\""
                                    "/etc/yum/repos.d").format(repo_file)
                        bash_script.write(six.b(copy_cmd))
                        bash_script.flush()
                        self._executor.execute_success(["bash",
                                                        bash_script.name])

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        if len(package_names):
            _run_task(self._executor,
                      """Install packages""",
                      ["yum", "install", "-y"] + package_names,
                      detail=_format_package_list(package_names))


def extract_tarfile(name):
    """Extract a tarfile.

    We attempt to do this in python, but work around bugs in the tarfile
    implementation on various operating systems.
    """
    # LZMA extraction in broken on Travis-CI with OSX. Shell out to
    # tar instead.
    if platform.system() == "Darwin" and os.path.splitext(name)[1] == ".xz":
        proc = subprocess.Popen(["tar", "-xJvf", name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        (stdout, stderr) = proc.communicate()
        ret = proc.wait()

        if ret != 0:
            raise RuntimeError("""Extraction of {archive} failed """
                               """with {ret}\n{stdout}\n{stderr}"""
                               """""".format(archive=name,
                                             ret=ret,
                                             stdout=stdout.decode(),
                                             stderr=stderr.decode()))
        return

    with tarfile.open(name=name) as tarfileobj:
        tarfileobj.extractall()


class Brew(PackageSystem):
    """Homebrew packaging system for OS X."""

    def __init__(self, executor):
        """Initialize homebrew for executor."""
        super(Brew, self).__init__()
        self._executor = executor

    def add_repositories(self, repos):
        """Add repositories as specified at repos.

        Adds repositories using brew tap.
        """
        for repo in repos:
            _run_task(self._executor,
                      """Adding repository {0}""".format(repo),
                      ["brew", "tap", repo])

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        from six.moves import shlex_quote  # suppress(import-error)
        from six.moves.urllib.parse import urlparse  # suppress(import-error)

        # Separate out into packages that need to be downloaded with
        # brew and those that can be downloaded directly
        tar_packages = [p for p in package_names if urlparse(p).scheme]
        brew_packages = [p for p in package_names if not urlparse(p).scheme]

        if len(brew_packages):
            _run_task(self._executor,
                      """Updating repositories""",
                      ["brew", "update"])

            _run_task(self._executor,
                      """Install packages""",
                      ["brew", "install"] + brew_packages,
                      detail=_format_package_list(brew_packages))

        for tar_pkg in tar_packages:
            _report_task("""Install {}""".format(tar_pkg))
            with tempdir.TempDir() as download_dir:
                with directory.Navigation(download_dir):
                    download.download_file(tar_pkg)
                    extract_tarfile(os.path.basename(tar_pkg))
                    # The shell provides an easy way to do this, so just
                    # use subprocess to call out to it.
                    extracted_dir = [d for d in os.listdir(download_dir)
                                     if d != os.path.basename(tar_pkg)][0]
                    subprocess.check_call("cp -r {src}/* {dst}".format(
                        src=shlex_quote(extracted_dir),
                        dst=self._executor.root_filesystem_directory()
                    ), shell=True)


class Choco(PackageSystem):
    """Chocolatey packaging system for Windows."""

    def __init__(self, executor):
        """Initialize choco for executor."""
        super(Choco, self).__init__()
        self._executor = executor

    def add_repositories(self, repos):
        """Add repositories as specified at repos.

        This function doesn't do anything on Choco at the moment.
        """
        pass

    def install_packages(self, package_names):
        """Install all packages in list package_names."""
        _run_task(self._executor,
                  """Install packages""",
                  ["choco", "install", "-fy", "-m"] + package_names,
                  detail=_format_package_list(package_names))
