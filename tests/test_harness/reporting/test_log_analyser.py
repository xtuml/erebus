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
    parse_log_string_to_pv_results_dataframe,
    logs_validity_df_to_results
)
from test_harness.utils import check_dict_equivalency


# test resources folder
test_resources = Path(__file__).parent.parent / "test_files"

# unhappy logs file
unhappy_logs_file = test_resources / "unhappy_jobs_test.logs"

# verifier parse logs
verifier_parse_logs = test_resources / "Verifier_parse_test.log"

# reception log file validity
reception_json_validity = test_resources / "Reception_json_validity_test.log"


def test_parse_log_string_to_pv_results_dataframe() -> None:
    """Tests `parse_log_string_to_pv_results_dataframe`"""
    pv_results = parse_log_string_to_pv_results_dataframe(
        verifier_parse_logs.read_text()
    )
    assert len(pv_results) == 5
    expected_job_ids = [
        ("13021f1d-0854-4948-ab55-c9f5b5977d23", True),
        ("91adcba7-05ff-4361-9be7-c0de8e22b9f7", True),
        ("854ca735-d000-49d9-941e-947d2728848e", False),
        ("b5498ed4-a532-48c9-885f-d01671f95d60", False),
        ("f5e96c8b-9bc1-4882-a482-72c36d4e767c", False),
    ]
    for job_id, pv_result in expected_job_ids:
        assert job_id in pv_results.index
        assert all(pv_results.loc[job_id, "PVResult"]) == pv_result


def test_parse_log_string_to_pv_results_dataframe_reception_log_file() -> None:
    """Tests `parse_log_string_to_pv_results_dataframe`"""
    event_id_job_id_map = {
        "20b46747-81cb-487e-a12b-60fe3970f9aa": "job_1",
        "cc13d7fa-eb8a-4cfc-b41e-a1146783360f": "job_2",
        "a7448bda-84ca-4924-b3d2-9816b408b4a1": "job_3",
        "54c51bcf-6a61-43d8-bb7b-7f462a5cac01": "job_4"
    }
    pv_results = parse_log_string_to_pv_results_dataframe(
        reception_json_validity.read_text(),
        event_id_job_id_map=event_id_job_id_map
    )
    assert len(pv_results) == 4
    expected_job_ids = [
        ("job_1", True),
        ("job_2", False),
        ("job_3", True),
        ("job_4", False),
    ]
    for job_id, pv_result in expected_job_ids:
        assert job_id in pv_results.index
        assert all(pv_results.loc[job_id, "PVResult"]) == pv_result


def test_parse_log_string_to_pv_results_dataframe_svdc_failures() -> None:
    """Tests `parse_log_string_to_pv_results_dataframe` with SVDC failures"""
    log_string = (
        "2023-11-02T18:44:44.951533Z 3 svdc_job_failed : FailureReason = one"
        " or more constraint checks have failed : JobId ="
        " 3843e246-7940-4e70-b173-4840cfc21386 with Job Name = simple_AND_job"
        + "\n"
        + "svdc_job_failed : FailureReason = Invalid audit event definition"
        " for a start event in job definition = simple_AND_job since the"
        " occurrenceNumberInSequence is expected to be 1 : JobId ="
        " 3f01aeca-7b4a-4288-9078-8ce32d36fec7 with Job Name ="
        " simple_AND_job"
        + "\n"
        + "2023-10-26T15:01:47.148184Z 1 svdc_job_failed : FailureReason ="
        " JobId = b5498ed4-a532-48c9-885f-d01671f95d60 : ApplicationName ="
        " default_application_name : EventType = SpyEvent : FailureReason ="
        " Event type is not allowed to be reported for application : JobId ="
        " b5498ed4-a532-48c9-885f-d01671f95d60"
        + "\n"
        + "2023-10-26T15:01:46.154341Z 1 svdc_job_failed : FailureReason = An"
        " event starting a new sequence has been received but there is no"
        " matching start event definition for Job ="
        " 854ca735-d000-49d9-941e-947d2728848e, with audit event type = B :"
        " JobId = 854ca735-d000-49d9-941e-947d2728848e"
        + "\n"
        + "svdc_job_failed : FailureReason = JobId ="
        " a5239839-c2e3-474b-81ab-88a007eb956f : EventType = SpyEvent :"
        " FailureReason = Event type is not allowed for job name, Job Name ="
        " simple_AND_job : JobId = a5239839-c2e3-474b-81ab-88a007eb956f with"
        " Job Name = simple_AND_job"
    )
    pv_results = parse_log_string_to_pv_results_dataframe(
        log_string=log_string
    )
    assert len(pv_results) == 5
    expected_job_ids = [
        ("3843e246-7940-4e70-b173-4840cfc21386", False),
        ("3f01aeca-7b4a-4288-9078-8ce32d36fec7", False),
        ("b5498ed4-a532-48c9-885f-d01671f95d60", False),
        ("854ca735-d000-49d9-941e-947d2728848e", False),
        ("a5239839-c2e3-474b-81ab-88a007eb956f", False),
    ]
    for job_id, pv_result in expected_job_ids:
        assert job_id in pv_results.index
        assert all(pv_results.loc[job_id, "PVResult"]) == pv_result


def test_parse_log_string_to_pv_results_dataframe_un_happy() -> None:
    """Tests `parse_log_string_to_pv_results_dataframe` with unhappy logs"""
    pv_results = parse_log_string_to_pv_results_dataframe(
        unhappy_logs_file.read_text()
    )
    assert len(pv_results) == 2
    expected_job_ids = [
        ("e365e78d-1b7a-49f1-b12d-165a64bae217", True),
        ("296fea2e-db4b-48d2-b111-223694a5a64b", False),
    ]
    for job_id, pv_result in expected_job_ids:
        assert job_id in pv_results.index
        assert all(pv_results.loc[job_id, "PVResult"]) == pv_result


def test_logs_validity_df_to_results_json_validity(
    validity_df_json_validity: DataFrame,
) -> None:
    """Tests `logs_validity_df_to_results` with json validity

    :param validity_df_json_validity: Fixture providing a DataFrame of validity
    :type validity_df_json_validity: :class:`DataFrame`
    """
    event_id_job_id_map = {
        "20b46747-81cb-487e-a12b-60fe3970f9aa": "job_1",
        "cc13d7fa-eb8a-4cfc-b41e-a1146783360f": "job_2",
        "a7448bda-84ca-4924-b3d2-9816b408b4a1": "job_3",
        "54c51bcf-6a61-43d8-bb7b-7f462a5cac01": "job_4"
    }
    results = logs_validity_df_to_results(
        log_string=reception_json_validity.read_text(),
        validity_df=validity_df_json_validity,
        event_id_job_id_map=event_id_job_id_map
    )
    assert len(results) == 4
    expected_results = {
        "job_1": "Pass",
        "job_2": "Fail",
        "job_3": "Fail",
        "job_4": "Pass",
    }
    for job_id, result in expected_results.items():
        assert job_id in results.index
        assert results.loc[job_id, "TestResult"] == result


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
    expected_verifier_grok_results: list[dict[str, str]],
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
        results, expected_verifier_grok_results
    ):
        check_dict_equivalency(result, expected_result)


def test_yield_grok_metrics_from_files(
    grok_priority_patterns: list[Grok],
    expected_verifier_grok_results: list[dict[str, str]],
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
            [log_file_path] * 2, grok_priority_patterns
        )
    )
    for result, expected_result in zip(
        results, expected_verifier_grok_results * 2
    ):
        check_dict_equivalency(result, expected_result)
