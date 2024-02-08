#!/usr/bin/env python
"""Setup script for installation
"""
from setuptools import setup

setup(
    name='Erebus',
    version='1.0.0',
    description=(
        'General purpose Test Harness supporting the munin project software'
    ),
    author='Freddie Mather',
    author_email='freddie.mather@smartdcs.co.uk',
    packages=[
        'test_harness',
        'test_harness.simulator',
        'test_harness.protocol_verifier',
        'test_harness.message_buses',
    ],
)
