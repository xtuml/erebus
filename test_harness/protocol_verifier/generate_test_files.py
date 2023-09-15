"""Methods for generating test files using test event generator
"""
from typing import Generator, Any
from itertools import chain

import matplotlib.pyplot as plt
from test_event_generator.io.run import (  # pylint: disable=E0401
    puml_file_to_test_events
)
from test_harness.config.config import TestConfig


def generate_test_events_from_puml_file(
    puml_file_path: str,
    test_config: TestConfig
) -> dict[
    str,
    dict[
        str,
        tuple[
            Generator[
                tuple[list[dict], list[str], plt.Figure | None, str],
                Any,
                None
            ],
            bool
        ]
    ]
]:
    """Method to generate test cases given a puml file path.

    :param puml_file_path: The path of the puml file
    :type puml_file_path: `str`
    :param test_config: Configuration for tests
    :type test_config: :class:`TestConfig`
    :return: Returns the dictionary of job defintions mapped to test cases
    :rtype: `dict`[ `str`, `dict`[ `str`, `tuple`[ :class:`Generator`[
    `tuple`[`list`[`dict`], `list`[`str`], :class:`plt`.`Figure` | `None`,
    `str`], `Any`, `None` ], `bool` ] ] ]
    """
    test_events = puml_file_to_test_events(
        file_path=puml_file_path,
        **test_config.event_gen_options
    )
    return test_events


def generate_test_events_from_puml_files(
    puml_file_paths: list[str],
    test_config: TestConfig
) -> dict[
    str,
    dict[
        str,
        tuple[
            Generator[
                tuple[list[dict], list[str], plt.Figure | None, str],
                Any,
                None
            ],
            bool
        ]
    ]
]:
    """Method to generate test cases given a list of puml file paths

    :param puml_file_paths: List of paths of puml files
    :type puml_file_paths: `list`[`str`]
    :param test_config: Configuration for tests
    :type test_config: :class:`TestConfig`
    :return: Returns the dictionary of job defintions mapped to test cases
    :rtype: `dict`[ `str`, `dict`[ `str`, `tuple`[ :class:`Generator`[
    `tuple`[`list`[`dict`], `list`[`str`], :class:`plt`.`Figure` | `None`,
    `str`], `Any`, `None` ], `bool` ] ] ]
    """
    return dict(chain.from_iterable(
        generate_test_events_from_puml_file(
            puml_file_path,
            test_config
        ).items()
        for puml_file_path in puml_file_paths
    ))
