#!/usr/bin/env python
"""Setup script for installation
"""
from setuptools import setup

main_packages = [
        'test_harness',
        'test_harness.simulator',
        'test_harness.message_buses',
        'test_harness.config',
        'test_harness.metrics',
        'test_harness.async_management',
        'test_harness.reporting',
        'test_harness.requests_th',
        'test_harness.results',
        'test_harness.process_manager',
    ]
protocol_verifier_packages = [
    'test_harness.protocol_verifier',
    # 'test_harness.protocol_verifier.config',
    # 'test_harness.protocol_verifier.metrics_and_events',
    # 'test_harness.protocol_verifier.mocks',
    # 'test_harness.protocol_verifier.pv_config',
    # 'test_harness.protocol_verifier.reporting',
    # 'test_harness.protocol_verifier.requests',
    # 'test_harness.protocol_verifier.results',
    # 'test_harness.protocol_verifier.testing_suite',
    # 'test_harness.protocol_verifier.tests',
    # 'test_harness.protocol_verifier.utils',
    ]

setup(
    name='test_harness',
    version='1.1.4',
    description=(
        'General purpose Test Harness supporting the munin project software'
    ),
    author='Freddie Mather',
    author_email='freddie.mather@smartdcsit.co.uk',
    packages=main_packages,
    package_dir={"test_harness": "test_harness"},
    include_package_data=True,
    extras_require={
        'protocol_verifier': protocol_verifier_packages,
    },
)
