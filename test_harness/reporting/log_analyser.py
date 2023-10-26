# pylint: disable=R0911
"""Methods to analyse logs
"""
from typing import TextIO, Any, Generator

import pandas as pd
from pygrok import Grok


pv_success_groks = (
    Grok(
        "svdc_job_success :"
        " JobId = %{UUID:JobId} : JobName = %{WORD:JobName}"
    ),
)

pv_failure_groks = (
    Grok(
        "svdc_job_failed"
        " : FailureReason = %{FAILURE_REASON:FailureReason}"
        "for Job = %{UUID:JobId}",
        custom_patterns={
            "FAILURE_REASON": "[a-zA-Z ]+"
        }
    ),
    Grok(
        "aeordering_job_failed"
        " : JobId = %{UUID:JobId}"
        " : FailureReason = %{FAILURE_REASON:FailureReason}",
        custom_patterns={
            "FAILURE_REASON": "[a-zA-Z ]+"
        }
    ),
    Grok(
        "svdc_job_alarm"
        " : Alarm Condition = ALARM: %{FAILURE_REASON:Alarm}"
        " : JobId = %{UUID:JobId} with Job Name = %{FAILURE_REASON:JobName}",
        custom_patterns={
            "FAILURE_REASON": "[a-zA-Z ]+"
        }
    ),
)


def logs_validity_df_to_results(
    log_string: str, validity_df: pd.DataFrame
) -> pd.DataFrame:
    """Method to obtain a test results dataframe from a string representing
    the Protocol Verifier "Verifier.log"

    :param log_string: log file string
    :type log_string: `str`
    :param validity_df: Dataframe with JobID and Validity of the Job. Extra
    information on the test case can be given
    :type validity_df: :class:`pd`.`DataFrame`
    :return: Returns a dataframe of results with fields (no limited to):
    * JobId - the id of the job
    * Validity - The validity of the job
    * PVResult - Protocol Verifier Result
    * TestResult - The outcome of the test
    :rtype: :class:`pd`.`DataFrame`
    """
    # get pv results
    pv_results_df = parse_log_string_to_pv_results_dataframe(log_string)
    # get test results
    results_df = get_job_id_failure_successes(pv_results_df, validity_df)
    return results_df


def parse_log_string_to_pv_results_dataframe(log_string: str) -> pd.DataFrame:
    """Method to parse verifier log string into a dataframe

    :param log_string: log file string
    :type log_string: `str`
    :return: DataFrame of Protocol verifier results
    :rtype: :class:`pd`.`DataFrame`
    """
    # split log string into lines
    log_lines = log_string.splitlines()
    job_success = []
    job_failed = []
    for line in log_lines:
        success_grok = grok_line_priority(line, pv_success_groks)
        if success_grok:
            job_success.append(success_grok)
            continue
        failure_grok = grok_line_priority(line, pv_failure_groks)
        if failure_grok:
            job_failed.append(failure_grok)
    # create dataframes for success and failures
    job_success_df = pd.DataFrame.from_records(
        job_success
    ).drop_duplicates(ignore_index=True)
    job_success_df["PVResult"] = True
    job_failed_df = pd.DataFrame.from_records(
        job_failed
    ).drop_duplicates(ignore_index=True)
    job_failed_df["PVResult"] = False
    # concatenate datframes
    results_df = pd.concat(
        [job_success_df, job_failed_df],
        sort=False,
    )
    # aggregate results by job id
    cols = list(results_df.columns)
    # if JobId not in columns update
    if "JobId" not in cols:
        results_df["JobId"] = None
    results_df = results_df.groupby("JobId").agg(
        {col: list for col in cols if col != "JobId"}
    )
    return results_df


def column_data_string_to_header_cell_dict(
    data_string: str,
) -> tuple[str, str]:
    """Method to create a header and cell value from a string of data from logs

    :param data_string: String of data with header and value separated by " = "
    :type data_string: `str`
    :return: Returns a tuple with header and the value
    :rtype: `tuple`[`str`, `str`]
    """
    data_string = data_string.replace("\n", "")
    split = data_string.split(" = ")
    header = split[0].strip()
    cell = "".join(split[1:])
    return header, cell


def line_split_to_dict(line_split: list[str]) -> dict[str, str]:
    """Method to create a dict of header and value in a split line

    :param line_split: The line split into header value strings
    :type line_split: `list`[`str`]
    :return: Returns a dictionary of header valu pairs
    :rtype: `dict`[`str`, `str`]
    """
    line_dict: dict[str, str] = {}
    for entry in line_split:
        header, cell = column_data_string_to_header_cell_dict(entry)
        line_dict[header] = cell
    return line_dict


def get_job_id_failure_successes(
    data_frame_pv_results_df: pd.DataFrame, job_id_validity_df: pd.DataFrame
) -> pd.DataFrame:
    """Method to check parsed Protocol Verifier results against the validity
    of job ids to provide results of "Pass", "Fail" and
    "Inconclusive|No SVDC Success|No Notification Failure". Reasons for PV
    failure are also provided

    :param data_frame_pv_results_df: :class:`DataFrame` containing PV results
    with job id. May be multiple rows with same Job ID
    :type data_frame_pv_results_df: :class:`pd.DataFrame`
    :param job_id_validity_df: :class:`DataFrame` containing JobID and its
    validity. Extra meta-data on file name, category of test type may also be
    added arbitrarily
    :type job_id_validity_df: :class:`pd.DataFrame`
    :return: Returns a :class:`DataFrame` with required fields (but may not be
    only fields):
    * JobID
    * Validity
    * PVResult
    * TestResult
    :rtype: :class:`pd.DataFrame`
    """
    data_frame_result = job_id_validity_df.merge(
        data_frame_pv_results_df, how="left", left_index=True, right_index=True
    )
    data_frame_result["TestResult"] = data_frame_result.apply(
        lambda x: check_test_result(x["Validity"], x["PVResult"]), axis=1
    )
    return data_frame_result


def check_test_result(
    validity: bool, pv_results: list[bool] | None | float
) -> str:
    """Method to check the PV result against validity of the job

    :param validity: Boolean indicating if the job is valid or invalid
    :type validity: `bool`
    :param pv_results: A list of the results from the protocol verifier for
    that job
    :type pv_results: `list`[`bool`] | `None` | `float`
    :return: Returns a string with the outcome of the test.
    :rtype: `str`
    """
    if not pv_results or isinstance(pv_results, float):
        return "Inconclusive|No SVDC Success|No Notification Failure"
    if validity:
        if all(pv_results):
            return "Pass"
        if any(pv_results):
            return "Inconclusive|SVDC Success|Notified Failure"
        return "Fail"
    if all(pv_results):
        return "Fail"
    if any(pv_results):
        return "Inconclusive|SVDC Success|Notified Failure"
    return "Pass"


def grok_line_priority(
    line: str, grok_priorities: list[Grok]
) -> dict[str, str | Any] | None:
    """Method to get a grok match (if there is one) from a line given a list
    of grok patterns in order of their priority

    :param line: The line to attempt to match
    :type line: `str`
    :param grok_priorities: List of grok patterns to match in priority order
    :type grok_priorities: `list`[:class:`Grok`]
    :return: Returns a dictionary that relates to the grok match patterns given
    :rtype: `dict`[`str`, `str` | `Any`] | `None`
    """
    for grok in grok_priorities:
        grok_match = grok.match(line)
        if grok_match:
            return grok_match
    return grok_match


def yield_grok_metrics_from_file_buffer(
    file_buffer: TextIO, grok_priorities: list[Grok]
) -> Generator[dict[str, str | Any], Any, None]:
    """Method to generate grok matches (if there are any) from a file buffer
    given a list of grok patterns in order of their priority

    :param file_buffer: The file buffer to find matches in
    :type file_buffer: :class:`TextIO`
    :param grok_priorities: List of grok patterns to match in priority order
    :type grok_priorities: `list`[:class:`Grok`]
    :yield: Yields dictionaries that relate to the grok match patterns given
    :rtype: :class:`Generator`[`dict`[`str`, `str` | `Any`], `Any`, `None`]
    """
    for line in file_buffer:
        grok_match = grok_line_priority(line, grok_priorities)
        if grok_match:
            yield grok_match


def yield_grok_metrics_from_files(
    file_paths: list[str], grok_priorities: list[Grok]
) -> Generator[dict[str, str | Any], Any, None]:
    """Method to generate grok matches (if there are any) from a list of file
    paths given a list of grok patterns in order of their priority

    :param file_paths: _description_
    :type file_paths: list[str]
    :param grok_priorities: List of grok patterns to match in priority order
    :type grok_priorities: `list`[:class:`Grok`]
    :yield: Yields dictionaries that relate to the grok match patterns given
    :rtype: :class:`Generator`[`dict`[`str`, `str` | `Any`], `Any`, `None`]
    """
    for file in file_paths:
        with open(file, "r", encoding="utf-8") as file_buffer:
            yield from yield_grok_metrics_from_file_buffer(
                file_buffer, grok_priorities
            )
