# /setup.py
#
# Installation and setup script for psqtraviscontainer
#
# See /LICENCE.md for Copyright information
"""Installation and setup script for psqtraviscontainer."""

import platform

from setuptools import find_packages, setup

INSTALL_EXTRAS = []
DEPENDENCY_LINKS = []

if platform.system() != "Windows":
    INSTALL_EXTRAS.extend([
        "urlgrabber==3.10.1",
        "pycurl",
        "python-debian"
    ])
    DEPENDENCY_LINKS.append("https://github.com/smspillaz/urlgrabber/"
                            "tarball/master#egg=urlgrabber-3.10.1")

setup(name="psqtraviscontainer",
      version="0.0.4",
      description="Polysquare Travis-CI Container Root",
      long_description_markdown_filename="README.md",
      author="Sam Spilsbury",
      author_email="smspillaz@gmail.com",
      classifiers=["Development Status :: 3 - Alpha",
                   "Intended Audience :: Developers",
                   "Topic :: Software Development :: Build Tools",
                   "License :: OSI Approved :: MIT License",
                   "Programming Language :: Python :: 3",
                   "Programming Language :: Python :: 3.3",
                   "Programming Language :: Python :: 3.4"],
      url="http://github.com/polysquare/polysquare-travis-container",
      license="MIT",
      keywords="development travis",
      packages=find_packages(exclude=["test"]),
      dependency_links=DEPENDENCY_LINKS,
      install_requires=["configargparse",
                        "six",
                        "shutilwhich",
                        "colorama",
                        "tempdir",
                        "termcolor"] + INSTALL_EXTRAS,
      extras_require={
          "green": [
              "coverage",
              "testtools",
              "shutilwhich",
              "nose",
              "nose-parameterized",
              "mock",
              "setuptools-green",
              "tempdir"
          ],
          "polysquarelint": [
              "polysquare-setuptools-lint"
          ],
          "upload": [
              "setuptools-markdown"
          ]
      },
      entry_points={
          "console_scripts": [
              "psq-travis-container-create=psqtraviscontainer.create:main",
              "psq-travis-container-exec=psqtraviscontainer.use:main"
          ]
      },
      test_suite="nose.collector",
      zip_safe=True,
      include_package_data=True)
