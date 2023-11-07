"""Methods for generating test files using test event generator
"""
from typing import (
    Any, Iterator, NamedTuple, Self
)
from itertools import chain
import json

from test_event_generator.io.run import (  # pylint: disable=E0401
    puml_file_to_test_events
)

from test_harness.config.config import TestConfig
from test_harness.protocol_verifier.types import (
    TestJobFile, TemplateJobsDataAndValidityTuple, GeneratedJobData
)


def generate_test_events_from_puml_file(
    puml_file_path: str,
    test_config: TestConfig
) -> dict[
    str,
    dict[
        str,
        TemplateJobsDataAndValidityTuple
    ]
]:
    """Method to generate test cases given a puml file path.

    :param puml_file_path: The path of the puml file
    :type puml_file_path: `str`
    :param test_config: Configuration for tests
    :type test_config: :class:`TestConfig`
    :return: Returns the dictionary of job defintions mapped to test cases
    :rtype: `dict`[ `str`, `dict`[ `str`, `TemplateJobsDataAndValidityTuple`]]
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
        TemplateJobsDataAndValidityTuple
    ]
]:
    """Method to generate test cases given a list of puml file paths

    :param puml_file_paths: List of paths of puml files
    :type puml_file_paths: `list`[`str`]
    :param test_config: Configuration for tests
    :type test_config: :class:`TestConfig`
    :return: Returns the dictionary of job defintions mapped to test cases
    :rtype: `dict`[ `str`, `dict`[ `str`, `TemplateJobsDataAndValidityTuple`]]]
    """
    return dict(chain.from_iterable(
        generate_test_events_from_puml_file(
            puml_file_path,
            test_config
        ).items()
        for puml_file_path in puml_file_paths
    ))


def get_test_events_from_test_file_jsons(
    test_file_paths: list[str]
) -> dict[
    str,
    dict[
        str,
        TemplateJobsDataAndValidityTuple
    ]
]:
    """Method to generate the dictionary that holds the template test events
    lists along with their validity and sequence name type

    :param test_file_paths: The paths of the test files
    :type test_file_paths: `list`[`str`]
    :return: Returns a results holder dictionary that can be used in the test
    harness
    :rtype: `dict`[ `str`, `dict`[ `str`,
    `TemplateJobsDataAndValidityTuple` ] ]
    """
    test_files_holder: dict[
        str,
        dict[
            str,
            TemplateJobsDataAndValidityTuple
        ]
    ] = {}
    for test_file_path in test_file_paths:
        load_test_file_data_json_into_test_file_holder(
            test_file_path,
            test_files_holder
        )
    return test_files_holder


def load_test_file_data_json_into_test_file_holder(
    test_file_path: str,
    test_files_holder: dict[
        str,
        dict[
            str,
            TemplateJobsDataAndValidityTuple
        ]
    ]
) -> None:
    """Method to load a test file and update the test events holder

    :param test_file_path: The path of the test file
    :type test_file_path: `str`
    :param test_files_holder: Results holder dictionary that can be used in
    the test harness
    :type test_files_holder: `dict`[ `str`, `dict`[ `str`,
    `TemplateJobsDataAndValidityTuple` ] ]
    """
    with open(test_file_path, 'r', encoding="utf-8") as file:
        test_file_data: TestJobFile = json.load(file)
    update_test_files_holder_with_test_file(
        test_files_holder=test_files_holder,
        test_file_data=test_file_data
    )


class UpdateableIterator(Iterator):
    def __init__(self) -> None:
        self._data: list[Any] = []
        self._index = 0

    def add(self, data: Any) -> None:
        self._data.append(data)

    def __iter__(self) -> Self:
        return self

    def __next__(self):
        try:
            next_iter = self._data[self._index]
            self._index += 1
            return next_iter
        except IndexError:
            raise StopIteration


class SequenceTypeData(NamedTuple):
    """Named tuple that holds the job data, validity and options of
    the sequence type
    """
    job_sequences: (
        Iterator[GeneratedJobData] | UpdateableIterator[GeneratedJobData]
    )
    """An Iterator of the generated job sequences and data
    """
    validity: bool
    """The validity of the generated job sequences
    """
    options: dict[str, Any] = {}
    """The options for the template jobs
    """


def update_test_files_holder_with_test_file(
    test_files_holder: dict[
        str,
        dict[
            str,
            SequenceTypeData
        ]
    ],
    test_file_data: TestJobFile
) -> None:
    """Method to update the test file holder with the test file

    :param test_files_holder: Results holder dictionary that can be used in
    the test harness
    :type test_files_holder: `dict`[ `str`, `dict`[ `str`, `SequenceTypeData`]]
    :param test_file_data: The test file data as a python dictionary
    :type test_file_data: :class:`TestJobFile`
    """
    if test_file_data["job_name"] not in test_files_holder:
        test_files_holder[test_file_data["job_name"]] = {}
    if test_file_data["sequence_type"] not in test_files_holder[
        test_file_data["job_name"]
    ]:
        test_files_holder[
           test_file_data["job_name"]
        ][test_file_data["sequence_type"]] = SequenceTypeData(
            job_sequences=UpdateableIterator(),
            validity=test_file_data["validity"],
            options={} if "options" not in test_file_data else (
                test_file_data["options"]
            )
        )

    test_files_holder[
        test_file_data["job_name"]
    ][test_file_data["sequence_type"]].job_sequences.add(
        (
            test_file_data["job_file"],
            None,
            None,
            None
        )
    )
