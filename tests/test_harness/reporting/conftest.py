# pylint: disable=W0621
# pylint: disable=C0301
"""Fixtures for reporting tests
"""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def expected_results() -> pd.DataFrame:
    """Fixture providing dataframe of expected results

    :return: Returns dataframe of expected results
    :rtype: :class:`pd`.`DataFrame`
    """
    data = [
        [
            "job_1",
            "job_name",
            True,
            "ValidSols",
            "file_1",
            [np.nan],
            [True],
            "Pass",
        ],
        [
            "job_2",
            "job_name",
            True,
            "ValidSols",
            "file_2",
            ["It Failed"],
            [False],
            "Fail",
        ],
        [
            "job_3",
            "job_name",
            False,
            "StackedSols",
            "file_3",
            ["It Failed"] * 2,
            [False, False],
            "Pass",
        ],
        [
            "job_4",
            "job_name",
            False,
            "ANDConstraintBreak",
            "file_4",
            ["It Failed", np.nan],
            [False, True],
            "Inconclusive|SVDC Success|Notified Failure",
        ],
        [
            "job_5",
            "job_name",
            False,
            "MissingEdges",
            "file_5",
            np.nan,
            np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure",
        ],
    ]
    results_df = pd.DataFrame(
        data,
        columns=[
            "JobId",
            "SequenceName",
            "Validity",
            "Category",
            "FileName",
            "FailureReason",
            "PVResult",
            "TestResult",
        ],
    )
    results_df.set_index("JobId", inplace=True)
    return results_df


@pytest.fixture
def expected_junit_string() -> str:
    """Fixture providing an expected J-Unit xml string from expected results

    :return: Returns a string representation of the xml file
    :rtype: `str`
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<testsuites name="Tests Run"'
        ' tests="5" failures="1" errors="2">\n    <testsuite'
        ' name="job_name.False.ANDConstraintBreak" tests="1" failures="0"'
        ' errors="1">\n        <testcase name="JobId=job_4, FileName=file_4"'
        ' classname="job_name.False.ANDConstraintBreak">\n            <error'
        ' message="SVDC Success and PV failure" type="PVMisMatch">\n          '
        "      Protocol Verifier showed success and failure messages. PV"
        " Failure reasons below:\n                    It Failed;\n           "
        " </error>\n        </testcase>\n    </testsuite>\n    <testsuite"
        ' name="job_name.False.MissingEdges" tests="1" failures="0"'
        ' errors="1">\n        <testcase name="JobId=job_5, FileName=file_5"'
        ' classname="job_name.False.MissingEdges">\n            <error'
        ' message="No PV SVDC Success and no PV failure" type="PVMisMatch">\n '
        "               Time out was allowed but Protocol Verifier showed no"
        " success or failure messages\n            </error>\n       "
        " </testcase>\n    </testsuite>\n    <testsuite"
        ' name="job_name.False.StackedSols" tests="1" failures="0"'
        ' errors="0">\n        <testcase name="JobId=job_3, FileName=file_3"'
        ' classname="job_name.False.StackedSols" />\n    </testsuite>\n   '
        ' <testsuite name="job_name.True.ValidSols" tests="2" failures="1"'
        ' errors="0">\n        <testcase name="JobId=job_1, FileName=file_1"'
        ' classname="job_name.True.ValidSols" />\n        <testcase'
        ' name="JobId=job_2, FileName=file_2"'
        ' classname="job_name.True.ValidSols">\n            <failure'
        ' message="PV Result does not match validity" type="AssertionError">\n'
        "                PV Result was a fail when sequence is valid. PV"
        " failure reasons below:\n                    It Failed;\n           "
        " </failure>\n        </testcase>\n    </testsuite>\n</testsuites>"
    )


@pytest.fixture
def report_files_mapping(
    expected_results: pd.DataFrame,
    expected_junit_string: str,
    expected_html_string: str,
) -> dict[str, str | pd.DataFrame]:
    """Fixture providing a dictionary mapping file name to file

    :param expected_results: Fixture providing expected results dataframe
    :type expected_results: :class:`pd`.`DataFrame`
    :param expected_junit_string: Fixture providing expected junit string
    :type expected_junit_string: `str`
    :param expected_html_string: Fixture providing expected html string
    :type expected_html_string: `str`
    :return: Dictionary mapping filename to file
    :rtype: `dict`[`str`, `str` | :class:`pd`.`DataFrame`]
    """
    return {
        "test.csv": expected_results,
        "test.xml": expected_junit_string,
        "test.html": expected_html_string,
    }
