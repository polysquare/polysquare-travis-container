# /setup.py
#
# Installation and setup script for psqtraviscontainer
#
# See LICENCE.md for Copyright information
"""Installation and setup script for psqtraviscontainer."""

from setuptools import find_packages, setup

setup(name="psqtraviscontainer",
      version="0.0.1",
      description="Polysquare Travis-CI APT Container Root",
      long_description=("Creates a container that can be used to install"
                        " packages without root priviledges. Useful for"
                        " container mode in Travis-CI"),
      author="Sam Spilsbury",
      author_email="smspillaz@gmail.com",
      classifiers=["Development Status :: 3 - Alpha",
                   "Programming Language :: Python :: 2.7",
                   "Intended Audience :: Developers",
                   "Topic :: Software Development :: Build Tools",
                   "License :: OSI Approved :: MIT License",
                   "Programming Language :: Python :: 3"],
      url="http://github.com/polysquare/polysquare-travis-container",
      license="MIT",
      keywords="development travis",
      packages=find_packages(exclude=["tests"]),
      dependency_links=[
          ("https://github.com/smspillaz/urlgrabber/tarball/master"
           "#egg=urlgrabber-3.10.1")
      ],
      install_requires=["setuptools",
                        "pycurl",
                        "urlgrabber==3.10.1",
                        "patool",
                        "pyunpack",
                        "colorama",
                        "termcolor"],
      extras_require={
          "test": ["coverage",
                   "testtools",
                   "shutilwhich",
                   "nose",
                   "nose-parameterized",
                   "mock",
                   "tempdir"]
      },
      entry_points={
          "console_scripts": [
              "psq-travis-container-create=psqtraviscontainer.create:main",
              "psq-travis-container-exec=psqtraviscontainer.use:main"
          ]
      },
      test_suite="nose.collector",
      zip_safe=True)
