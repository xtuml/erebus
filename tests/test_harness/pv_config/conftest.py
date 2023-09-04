"""Fixtures for pv_config tests
"""
import pytest


@pytest.fixture
def expected_job_def_string() -> str:
    """Fixture to provide a string of an expected job def

    :return: Returns the expected json string
    :rtype: `str`
    """
    return (
        '{\n    "JobDefinitionName": "test_uml",\n    "Events": [\n        {\n'
        '            "EventName": "A",\n            "OccurrenceId": 0,\n      '
        '      "SequenceName": "test_uml",\n            "Application":'
        ' "default_application_name",\n            "SequenceStart": true\n    '
        '    },\n        {\n            "EventName": "B",\n           '
        ' "OccurrenceId": 0,\n            "SequenceName": "test_uml",\n       '
        '     "Application": "default_application_name",\n           '
        ' "PreviousEvents": [\n                {\n                   '
        ' "PreviousEventName": "A",\n                   '
        ' "PreviousOccurrenceId": 0\n                }\n            ]\n       '
        ' },\n        {\n            "EventName": "C",\n           '
        ' "OccurrenceId": 0,\n            "SequenceName": "test_uml",\n       '
        '     "Application": "default_application_name",\n           '
        ' "SequenceEnd": true,\n            "PreviousEvents": [\n             '
        '   {\n                    "PreviousEventName": "B",\n                '
        '    "PreviousOccurrenceId": 0\n                }\n            ]\n    '
        "    }\n    ]\n}"
    )
