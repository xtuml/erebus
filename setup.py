#!/usr/bin/env python
"""Setup script for installation
"""
from setuptools import setup

setup(
    name='test_harness',
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
        'test_harness.config',
        'test_harness.pv_config',
        'test_harness.metrics',
        'test_harness.async_management',
        'test_harness.reporting',
        'test_harness.requests',
        'test_harness.results',
        'test_harness.process_manager',
    ],
    package_data={
        'test_harness': [
            'test_harness/plus2json.pyz',
        ],
    }
)
