# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup, find_packages

setup(
    name='fwunit',
    version='0.1.0',
    description='Unit tests for firewall rules',
    author='Dustin J. Mitchell',
    author_email='dustin@mozilla.com',
    packages=find_packages(),
    install_requires=[
        "IPy",
        "nose",
    ],
    entry_points={
        "console_scripts": [
            'fwunit-prep = fwunit.scripts:prep',
        ],
    },
    license='MPL2',
)
