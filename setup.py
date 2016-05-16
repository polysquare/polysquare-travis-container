# /setup.py
#
# Installation and setup script for psqtraviscontainer
#
# See /LICENCE.md for Copyright information
"""Installation and setup script for psqtraviscontainer."""

import platform

from setuptools import find_packages, setup

INSTALL_EXTRAS = []

if platform.system() != "Windows":
    INSTALL_EXTRAS.extend([
        "python-debian"
    ])

setup(name="polysquare-travis-container",
      version="0.0.29",
      description="""Polysquare Travis-CI Container Root""",
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
      install_requires=["clint",
                        "configargparse",
                        "parse-shebang>=0.0.3",
                        "requests",
                        "six",
                        "shutilwhich",
                        "tempdir"] + INSTALL_EXTRAS,
      extras_require={
          "upload": [
              "setuptools-markdown"
          ]
      },
      entry_points={
          "console_scripts": [
              "psq-travis-container-create=psqtraviscontainer.create:main",
              "psq-travis-container-exec=psqtraviscontainer.use:main",
              "psq-travis-container-get-root=psqtraviscontainer.rootdir:main"
          ]
      },
      test_suite="nose.collector",
      zip_safe=True,
      include_package_data=True)
