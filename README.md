Polysquare Travis Container
===========================

Creates a container to install a mini-distribution without root access on the
Travis-CI container based infrastructure. The magic is done by combining
[`proot`](http://proot.me) and `qemu-user-mode`, which "fakes" the user-id to
zero and redirects rootfs access to our container. This works for most
applications.

Status
------

| Travis CI | Coverage |
|:---------:|:--------:|
|[![Travis](https://travis-ci.org/polysquare/polysquare-travis-container.svg?branch=master)](https://travis-ci.org/polysquare/polysquare-travis-container)|[![Coverage](https://coveralls.io/repos/polysquare/polysquare-travis-container/badge.png?branch=master)](https://coveralls.io/r/polysquare/polysquare-travis-container?branch=master)|

Caveats
-------

Polysquare Travis Container will not run on `pypy` due to the use of `pycurl`.

64 bit executables cannot be emulated on a 32 bit architecture and vice versa.

Creating a container
--------------------

Containers can be created with `psq-travis-container-create`:

    usage: psq-travis-container-create [-h] [--distro {Fedora,Debian,Ubuntu}]
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
      --distro {Fedora,Debian,Ubuntu}
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
                            (eg,ppa.launchpad.net)
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

    usage: psq-travis-container-exec [-h] [--distro {Fedora,Debian,Ubuntu}]
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
      --distro {Fedora,Debian,Ubuntu}
                            Distribution name to create container of
                            [env var: CONTAINER_DISTRO]
      --release RELEASE     Distribution release to create container of
                            [env var: CONTAINER_RELEASE]
      --arch {ppc,x86_64,x86,arm}
                            Architecture (all architectures other than the
                            system architecture will be emulated with qemu)
                            [env var: CONTAINER_ARCH]
      --cmd [CMD [CMD ...]]
                            Command to run inside of container

`CMD` is a space-separated command to be run inside the container. Executables
are resolved relative to the distribution container, so running `bash` would
run `CONTAINER_DIR/bin/bash` and not `/bin/bash` inside travis.

The `--container`, `--release` and `--arch` options are used to select a
pre-existing distribution container set up with `psq-travis-container-create`.

If executables are of a different architecture to the host architecture, they
will automatically be emulated with `qemu` for the target architecture.

