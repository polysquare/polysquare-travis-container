Polysquare Travis Container
===========================

Creates a self-contained package-management installation, without root access.

This allows you to install a pre-defined set of packages to a directory and
then execute commands using the packages installed in that directory.

Supports Windows, OS X and Linux.

On Windows and OS X, local versions of chocolatey and brew are installed
respectively, with packages installing to the specified folder. Commands
are executed with environment variables set such that the locally
installed packages will be used by any software built or installed
using the `psq-travis-container-exec` wrapper. Only the host architecture
is supported.

On Linux, [`proot`](http://proot.me) is used to "containerize" a downloaded
linux distribution, where the package manage operates only on the directory
in which the downloaded linux distribution exists. This allows you to
install packages using `apt-get` or `yum` without touching other
system files. `proot` allow allows for different architectures to be
specified as well, which are emulated transparently using the
`qemu-user-mode` tool.

Status
------

| Travis CI | AppVeyor | Coverage |
|:---------:|:--------:|:--------:|
|[![Travis](https://travis-ci.org/polysquare/polysquare-travis-container.svg?branch=master)](https://travis-ci.org/polysquare/polysquare-travis-container)|[![AppVeyor](https://ci.appveyor.com/api/projects/status/aqug38pkrai0guq0/branch/master?svg=true)](https://ci.appveyor.com/project/smspillaz/polysquare-travis-container-vd3yj/branch/master)|[![Coverage](https://coveralls.io/repos/polysquare/polysquare-travis-container/badge.png?branch=master)](https://coveralls.io/r/polysquare/polysquare-travis-container?branch=master)|

Caveats
-------

Polysquare Travis Container will not run on `pypy` due to the use of `pycurl`.

64 bit executables cannot be emulated on a 32 bit architecture.

Installation
------------

`polysquare-travis-container` can be installed using using `pip`, although it
is not hosted on PyPI.

Install it with:

    pip install \
    https://github.com/polysquare/polysquare-travis-container/tarball/master \
    --process-dependency-links

At the moment, `--process-dependency-links` needs to be passed because this
project uses a forked version of `urlgrabber`.

Creating a container
--------------------

Containers can be created with `psq-travis-container-create`:

    usage: psq-travis-container-create [-h] [--distro {Fedora,
                                                       Debian,
                                                       Ubuntu,
                                                       Windows,
                                                       OSX}]
                                       [--release RELEASE]
                                       [--arch {ppc,x86_64,x86,arm}]
                                       [--repositories REPOSITORIES]
                                       [--packages PACKAGES]
                                       CONTAINER_DIRECTORY

    Create a Travis CI container If an arg is specified in more than one place,
    then command-line values override environment variables which override
    defaults.

    positional arguments:
      CONTAINER_DIRECTORY   Directory to place container in

    optional arguments:
      -h, --help            show this help message and exit
      --distro {Fedora,Debian,Ubuntu,Windows,OSX}
                            Distribution name to create container of
                            [env var: CONTAINER_DISTRO]
      --release RELEASE     Distribution release to create container of
                            [env var: CONTAINER_RELEASE]
      --arch {ppc,x86_64,x86,arm}
                            Architecture (all architectures other than the
                            system architecture will be emulated with qemu)
                            [env var: CONTAINER_ARCH]
      --repositories REPOSITORIES
                            A file containing a list of repositories to add
                            before installing packages.  Special keywords will
                            control the operation of this file: {release}: The
                            distribution release (eg, precise) {ubuntu}: Ubuntu
                            archive URL {launchpad}: Launchpad PPA URL header
                            (eg, http://ppa.launchpad.net)
      --packages PACKAGES   A file containing a list of packages to install

The distribution filesystem itself is placed in a subdirectory of
`CONTAINER_DIRECTORY`, so multiple distribution configurations can be placed in
a single `CONTAINER_DIRECTORY`. A mini-distribution of `proot` will also be
placed in `CONTAINER_DIRECTORY`. This directory should be cached, for instance:

    cache:
      directories:
      - CONTAINER_DIRECTORY

Packages will only be installed if the container is being created and not
restored from the cache. To install additional packages, the travis caches
should be deleted.

Special directories like `/tmp` and `/home` are linked automatically, so you
can run binaries or scripts directly from the project root.

Using a container
-----------------

To run a command inside a container, use `psq-travis-container-exec`:

    usage: psq-travis-container-exec [-h] [--distro {Fedora,
                                                     Debian,
                                                     Ubuntu,
                                                     Windows,
                                                     OSX}]
                                     [--release RELEASE]
                                     [--arch {ppc,x86_64,x86,arm}] --cmd
                                     [CMD [CMD ...]]
                                     CONTAINER_DIRECTORY

    Use a Travis CI container If an arg is specified in more than one place,
    then command-line values override environment variables which override
    defaults.

    positional arguments:
      CONTAINER_DIRECTORY   Directory to place container in

    optional arguments:
      -h, --help            show this help message and exit
      --distro {Fedora,Debian,Ubuntu,Windows,OSX}
                            Distribution name to create container of
                            [env var: CONTAINER_DISTRO]
      --release RELEASE     Distribution release to create container of
                            [env var: CONTAINER_RELEASE]
      --arch {ppc,x86_64,x86,arm}
                            Architecture (all architectures other than the
                            system architecture will be emulated with qemu)
                            [env var: CONTAINER_ARCH]
      -- [CMD [CMD ...]]    Command to run inside of container

Executables in CMD are resolved relative to the distribution container, so
running `bash` would run `CONTAINER_DIR/bin/bash` and not `/bin/bash`
inside travis.

The `--container`, `--release` and `--arch` options are used to select a
pre-existing distribution container set up with `psq-travis-container-create`.

