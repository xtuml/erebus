#!/usr/bin/env python
"""Setup script for installation
"""
from setuptools import setup, find_packages

setup(
    name='test_harness',
    version='1.1.4',
    description=(
        'General purpose Test Harness supporting the munin project software'
    ),
    author='Freddie Mather',
    author_email='freddie.mather@smartdcsit.co.uk',
    packages=find_packages(),
    package_dir={"test_harness": "test_harness"},
    include_package_data=True,
)
