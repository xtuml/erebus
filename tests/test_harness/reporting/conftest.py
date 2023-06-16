"""Fixtures for reporting tests
"""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def validity_df() -> pd.DataFrame:
    """Fixture provide a dataframe with validity and job id amogsnt other
    fields

    :return: Returns a dataframe of validity and job id
    :rtype: :class:`pd`.`DataFrame`
    """
    data = [
        ["job_1", "job_1_name", True, "ValidSols", "file_1"],
        ["job_2", "job_2_name", True, "ValidSols", "file_2"],
        ["job_3", "job_3_name", False, "StackedSols", "file_3"],
        ["job_4", "job_4_name", False, "ANDConstraintBreak", "file_4"],
        ["job_5", "job_5_name", False, "MissingEdges", "file_5"]
    ]
    validity = pd.DataFrame(
        data,
        columns=["JobId", "JobName", "Validity", "Category", "FileName"]
    )
    validity.set_index("JobId", inplace=True)
    return validity


@pytest.fixture
def pv_results_df() -> pd.DataFrame:
    """Fixture to provide a mocked proctocol verifier results dataframe

    :return: Mocked PV results dataframe
    :rtype: :class:`pd`.`DataFrame`
    """
    data = [
        ["job_1", [np.nan], [True]],
        ["job_2", ["It Failed"], [False]],
        ["job_3", ["It Failed", "It Failed"], [False] * 2],
        ["job_4", ["It Failed", np.nan], [False, True]],
    ]
    results_df = pd.DataFrame(
        data=data,
        columns=["JobId", "Failure Reason", "PVResult"]
    )
    results_df.set_index("JobId", inplace=True)
    return results_df


@pytest.fixture
def expected_results() -> pd.DataFrame:
    """Fixture providing dataframe of expected results

    :return: Returns dataframe of expected results
    :rtype: :class:`pd`.`DataFrame`
    """
    data = [
        [
            "job_1", "job_1_name", True, "ValidSols", "file_1",
            [np.nan], [True], "Pass"
        ],
        [
            "job_2", "job_2_name", True, "ValidSols", "file_2",
            ["It Failed"], [False], "Fail"
        ],
        [
            "job_3", "job_3_name", False, "StackedSols", "file_3",
            ["It Failed"] * 2, [False, False], "Pass"
        ],
        [
            "job_4", "job_4_name", False, "ANDConstraintBreak", "file_4",
            ["It Failed", np.nan], [False, True],
            "Inconclusive|SVDC Success|Notified Failure"
        ],
        [
            "job_5", "job_5_name", False, "MissingEdges", "file_5",
            np.nan, np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure"
        ]
    ]
    results_df = pd.DataFrame(
        data,
        columns=[
            "JobId", "JobName", "Validity", "Category", "FileName",
            "Failure Reason", "PVResult", "TestResult"
        ]
    )
    results_df.set_index("JobId", inplace=True)
    return results_df
