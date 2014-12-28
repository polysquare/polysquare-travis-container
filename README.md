Polysquare Travis Container
===========================

Creates a container to install a mini-distribution without root access on the
Travis-CI container based infrastructure.

Status
------

| Travis CI (Ubuntu) | Coverage |
|--------------------|----------|
|[![Travis](https://travis-ci.org/polysquare/polysquare-travis-container.svg?branch=master)](https://travis-ci.org/polysquare/polysquare-travis-container)|[![Coverage](https://coveralls.io/repos/polysquare/polysquare-travis-container/badge.png?branch=master)](https://coveralls.io/r/polysquare/polysquare-travis-container?branch=master)|

Caveats
-------

Polysquare Travis Container only runs on Python 3.3 right now, due to
our fork of urlgrabber only working on Python 3.3. This shouldn't be too
much of a problem as its designed to be used on projects where Python is
not the main language.

Consider using the setup-languages.sh script from polysquare-ci-scripts
to enable python3.3 on a travis container.
