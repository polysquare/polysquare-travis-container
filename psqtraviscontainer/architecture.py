# /psqtraviscontainer/architecture.py
#
# Module which provides a helper for determining the names of various
# processor architectures on various distributions.
#
# See /LICENCE.md for Copyright information
"""Architecture handling."""

from collections import namedtuple

from six import with_metaclass

_ArchitectureType = namedtuple("_ArchitectureType",
                               "aliases debian universal qemu")

_X86_ARCHITECTURE = _ArchitectureType(aliases=["i386",
                                               "i486",
                                               "i586",
                                               "i686",
                                               "x86"],
                                      debian="i386",
                                      universal="x86",
                                      qemu="i386")
_X86_64_ARCHITECTURE = _ArchitectureType(aliases=["x86_64", "amd64"],
                                         debian="amd64",
                                         universal="x86_64",
                                         qemu="x86_64")
_ARM_HARD_FLOAT_ARCHITECTURE = _ArchitectureType(aliases=["arm",
                                                          "armel",
                                                          "armhf"],
                                                 debian="armhf",
                                                 universal="arm",
                                                 qemu="arm")
_POWERPC32_ARCHITECTURE = _ArchitectureType(aliases=["powerpc", "ppc"],
                                            debian="powerpc",
                                            universal="ppc",
                                            qemu="ppc")
_POWERPC64_ARCHITECTURE = _ArchitectureType(aliases=["ppc64el", "ppc64"],
                                            debian="ppc64el",
                                            universal="ppc64",
                                            qemu="ppc64")


class _AliasMetaclass(type):
    """A metaclass which provides an operator to convert arch strings."""

    @classmethod
    def __getitem__(cls,  # pylint:disable=bad-mcs-classmethod-argument
                    lookup):
        """Operator overload for [].

        If a special architecture for different platforms is not found, return
        a generic one which just has this architecture name
        """
        del cls

        overloaded_architectures = [_X86_ARCHITECTURE,
                                    _X86_64_ARCHITECTURE,
                                    _ARM_HARD_FLOAT_ARCHITECTURE,
                                    _POWERPC32_ARCHITECTURE,
                                    _POWERPC64_ARCHITECTURE]
        for arch in overloaded_architectures:
            if lookup in arch.aliases:
                return arch

        return _ArchitectureType(aliases=[lookup],
                                 debian=lookup,
                                 universal=lookup,
                                 qemu=lookup)


class Alias(with_metaclass(_AliasMetaclass, object)):
    """Implementation of _AliasMetaclass.

    Provides convenience methods to convert architecture strings
    between platforms.
    """

    @classmethod
    def debian(cls, lookup):
        """Convert to debian."""
        return cls[lookup].debian

    @classmethod
    def qemu(cls, lookup):
        """Convert to qemu."""
        return cls[lookup].qemu

    @classmethod
    def universal(cls, lookup):
        """Convert to universal."""
        return cls[lookup].universal
