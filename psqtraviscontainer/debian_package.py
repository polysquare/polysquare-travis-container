# /psqtraviscontainer/debian_package.py
#
# Functionality common to debian packages.
#
# See /LICENCE.md for Copyright information
"""Functionality common to debian packages."""

import tarfile

from contextlib import closing


def extract_deb_data(archive, extract_dir):
    """Extract archive to extract_dir."""
    # We may not have python-debian installed on all platforms
    from debian import arfile  # suppress(import-error)

    data_members = ["data.tar.gz", "data.tar.xz"]

    for data_mem in data_members:
        try:
            with closing(arfile.ArFile(archive).getmember(data_mem)) as member:
                with tarfile.open(fileobj=member,
                                  mode="r|*") as data_tar:
                    
                    import os
                    
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(data_tar, path=extract_dir)

            # Succeeded, break out here
            break
        except KeyError as error:
            if str(error) == "'{}'".format(data_mem):
                continue
            else:
                raise error
