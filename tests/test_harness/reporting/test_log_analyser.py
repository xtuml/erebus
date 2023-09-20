"""Test for log analysing
"""
import numpy as np
from pandas import DataFrame
import pytest

from test_harness.reporting.log_analyser import (
    check_test_result,
    get_job_id_failure_successes,
)


@pytest.mark.parametrize(
    "validity,pv_results,expected_result",
    [
        pytest.param(True, [True], "Pass", id="Valid Single PV Pass"),
        pytest.param(True, [True, True], "Pass", id="Valid Multiple PV Pass"),
        pytest.param(True, [False], "Fail", id="Valid Single PV Fail"),
        pytest.param(
            True, [False, False], "Fail", id="Valid Multiple PV Fail"
        ),
        pytest.param(
            True,
            [False, True],
            "Inconclusive|SVDC Success|Notified Failure",
            id="Valid Mixed PV Fail Pass"
        ),
        pytest.param(
            True,
            None,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Valid no pass or failure provided"
        ),
        pytest.param(
            True,
            np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Valid nan provided"
        ),
        pytest.param(False, [True], "Fail", id="Invalid Single PV Pass"),
        pytest.param(
            False, [True, True], "Fail", id="Invalid Multiple PV Pass"
        ),
        pytest.param(False, [False], "Pass", id="Invalid Single PV Fail"),
        pytest.param(
            False, [False, False], "Pass", id="Invalid Multiple PV Fail"
        ),
        pytest.param(
            False,
            [False, True],
            "Inconclusive|SVDC Success|Notified Failure",
            id="Invalid Mixed PV Fail Pass"
        ),
        pytest.param(
            False,
            None,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Invalid no pass or failure provided"
        ),
        pytest.param(
            False,
            np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Invalid nan provided"
        ),
    ],
)
def test_check_test_result(
    validity: bool,
    pv_results: list[bool] | None | float,
    expected_result: str
) -> None:
    """Test for `check_test_result` provided with parameterized tests

    :param validity: Boolean providing validity
    :type validity: `bool`
    :param pv_results: Result given from Protocol Verifier
    :type pv_results: `list`[`bool`] | `None` | `float`
    :param expected_result: The expected output from the check
    :type expected_result: `str`
    """
    result = check_test_result(
        validity=validity,
        pv_results=pv_results
    )
    assert result == expected_result


def test_get_job_id_failure_successes(
    validity_df: DataFrame,
    pv_results_df: DataFrame,
    expected_results: DataFrame
) -> None:
    """Tests `get_job_id_failure_successes`

    :param validity_df: Fixture providing DataFrame of validity and JobId
    :type validity_df: :class:`DataFrame`
    :param pv_results_df: Fixture providing DataFrame of PV results
    :type pv_results_df: :class:`DataFrame`
    :param expected_results: Fixture providing DataFrame of expected results
    :type expected_results: :class:`DataFrame`
    """
    results = get_job_id_failure_successes(
        data_frame_pv_results_df=pv_results_df,
        job_id_validity_df=validity_df
    )
    for job_id, row in expected_results.iterrows():
        for field, value in row.items():
            result_value = results.loc[str(job_id), str(field)]
            if isinstance(value, list) and isinstance(result_value, list):
                for test, expected in zip(
                    result_value,
                    value
                ):
                    if isinstance(expected, float):
                        assert isinstance(test, float)
                    else:
                        assert expected == test
            elif isinstance(value, float):
                assert isinstance(result_value, float)
            else:
                assert value == result_value
