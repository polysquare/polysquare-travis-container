Polysquare Travis Container
===========================

Creates a container to install a mini-distribution without root access on the
Travis-CI container based infrastructure.

Status
------

Caveats
-------

Polysquare Travis Container only runs on Python 2.7 right now, due to urlgrabber
only working on Python 2.7. This shouldn't be too much of a problem as its
designed to be used on projects where Python is not the main language.
