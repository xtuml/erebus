"""Test for log analysing
"""
from pathlib import Path
from typing import Literal

import numpy as np
from pandas import DataFrame
import pytest
from pygrok import Grok

from test_harness.reporting.log_analyser import (
    check_test_result,
    get_job_id_failure_successes,
    grok_line_priority,
    yield_grok_metrics_from_file_buffer,
    yield_grok_metrics_from_files,
)
from test_harness.utils import check_dict_equivalency


# test resources folder
test_resources = Path(__file__).parent.parent / "test_files"


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
            id="Valid Mixed PV Fail Pass",
        ),
        pytest.param(
            True,
            None,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Valid no pass or failure provided",
        ),
        pytest.param(
            True,
            np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Valid nan provided",
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
            id="Invalid Mixed PV Fail Pass",
        ),
        pytest.param(
            False,
            None,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Invalid no pass or failure provided",
        ),
        pytest.param(
            False,
            np.nan,
            "Inconclusive|No SVDC Success|No Notification Failure",
            id="Invalid nan provided",
        ),
    ],
)
def test_check_test_result(
    validity: bool, pv_results: list[bool] | None | float, expected_result: str
) -> None:
    """Test for `check_test_result` provided with parameterized tests

    :param validity: Boolean providing validity
    :type validity: `bool`
    :param pv_results: Result given from Protocol Verifier
    :type pv_results: `list`[`bool`] | `None` | `float`
    :param expected_result: The expected output from the check
    :type expected_result: `str`
    """
    result = check_test_result(validity=validity, pv_results=pv_results)
    assert result == expected_result


def test_get_job_id_failure_successes(
    validity_df: DataFrame,
    pv_results_df: DataFrame,
    expected_results: DataFrame,
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
        data_frame_pv_results_df=pv_results_df, job_id_validity_df=validity_df
    )
    for job_id, row in expected_results.iterrows():
        for field, value in row.items():
            result_value = results.loc[str(job_id), str(field)]
            if isinstance(value, list) and isinstance(result_value, list):
                for test, expected in zip(result_value, value):
                    if isinstance(expected, float):
                        assert isinstance(test, float)
                    else:
                        assert expected == test
            elif isinstance(value, float):
                assert isinstance(result_value, float)
            else:
                assert value == result_value


def test_grok_line_priority_single_pattern(
    log_file_string: Literal[
        "2023-09-28T19:27:23.434758Z 1 svdc_new_job_started…"
    ],
    grok_priority_patterns: list[Grok],
) -> None:
    """Tests `grok_line_priority` with a single grok pattern to search for

    :param log_file_string: Fixture providing a log file string
    :type log_file_string: `str`
    :param grok_priority_patterns: Fixture providing a list of grok patterns
    in priority order to search for
    :type grok_priority_patterns: `list`[`Grok`]
    """
    grok_result = grok_line_priority(
        log_file_string, grok_priority_patterns[1:]
    )
    assert grok_result
    assert len(grok_result) == 3
    assert all(key in grok_result for key in ["field", "timestamp", "job_id"])
    assert grok_result["field"] == "svdc_new_job_started"
    assert grok_result["timestamp"] == "2023-09-28T19:27:23.434758Z"
    assert grok_result["job_id"] == "eeba705f-eac4-467c-8826-bf31673e745f"


def test_grok_line_priority_prioritised_patterns(
    log_file_string: Literal[
        "2023-09-28T19:27:23.434758Z 1 svdc_new_job_started…"
    ],
    grok_priority_patterns: list[Grok],
) -> None:
    """Tests `grok_line_priority` with a two grok patterns to search for in
    priority order

    :param log_file_string: Fixture providing a log file string
    :type log_file_string: `str`
    :param grok_priority_patterns: Fixture providing a list of grok patterns
    in priority order to search for
    :type grok_priority_patterns: `list`[`Grok`]
    """
    grok_result = grok_line_priority(log_file_string, grok_priority_patterns)
    assert grok_result
    assert len(grok_result) == 3
    assert all(
        key in grok_result for key in ["field", "timestamp", "event_id"]
    )
    assert grok_result["field"] == "svdc_new_job_started"
    assert grok_result["timestamp"] == "2023-09-28T19:27:23.434758Z"
    assert grok_result["event_id"] == "3cf78438-8084-494d-8d7b-efd7ea46f7d4"


def test_yield_grok_metrics_from_file_buffer(
    grok_priority_patterns: list[Grok],
    expected_verifier_grok_results: list[dict[str, str]]
) -> None:
    """Tests `yield_grok_metrics_from_file_buffer`

    :param grok_priority_patterns: Fixture providing a list of grok patterns
    in priority order to search for
    :type grok_priority_patterns: `list`[`Grok`]
    :param expected_verifier_grok_results: Fixture providing the expected
    verifier grok results relating to the file `test_resources / "test.log"`
    :type expected_verifier_grok_results: `list`[`dict`[`str`, `str`]]
    """
    log_file_path = test_resources / "test.log"
    with open(log_file_path, "r", encoding="utf-8") as file_buffer:
        results = list(
            yield_grok_metrics_from_file_buffer(
                file_buffer, grok_priority_patterns
            )
        )
    for result, expected_result in zip(
        results,
        expected_verifier_grok_results
    ):
        check_dict_equivalency(
            result,
            expected_result
        )


def test_yield_grok_metrics_from_files(
    grok_priority_patterns: list[Grok],
    expected_verifier_grok_results: list[dict[str, str]]
) -> None:
    """Tests `yield_grok_metrics_from_files`

    :param grok_priority_patterns: Fixture providing a list of grok patterns
    in priority order to search for
    :type grok_priority_patterns: `list`[`Grok`]
    :param expected_verifier_grok_results: Fixture providing the expected
    verifier grok results relating to the file `test_resources / "test.log"`
    :type expected_verifier_grok_results: `list`[`dict`[`str`, `str`]]
    """
    log_file_path = test_resources / "test.log"
    results = list(
        yield_grok_metrics_from_files(
            [log_file_path] * 2,
            grok_priority_patterns
        )
    )
    for result, expected_result in zip(
        results,
        expected_verifier_grok_results * 2
    ):
        check_dict_equivalency(
            result,
            expected_result
        )
