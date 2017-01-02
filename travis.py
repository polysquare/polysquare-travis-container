#!/usr/bin/env python

import subprocess

print(subprocess.check_call(["bash", "-c",  "psq-travis-container-create --distro=Ubuntu --release=precise --arch=x86_64 --local container"]));
