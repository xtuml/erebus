"""__init__ file. Contains methods to create and save report files
"""
from pandas import DataFrame

from test_harness.reporting.log_analyser import logs_validity_df_to_results
from test_harness.reporting.report_results import (
    get_report_files_mapping_from_dataframe_report
)
from test_harness.reporting.report_delivery import deliver_test_report_files


def create_and_save_report_files(
    log_string: str,
    validity_df: DataFrame,
    test_name: str,
    output_directory_path: str
) -> None:
    """Method to create report files from logs and validity dataframe and save
    report files with a prefix in an output directory

    :param log_string: String representing the log files
    :type log_string: `str`
    :param validity_df: :class:`DataFrame` holding the information on the test
    files
    :type validity_df: :class:`DataFrame`
    :param test_name: The test name (or prefix) to give to the report files
    :type test_name: `str`
    :param output_directory_path: The path of the output directory to store
    the results
    :type output_directory_path: `str`
    """
    report_files_mapping = create_report_files(
        log_string=log_string,
        validity_df=validity_df,
        test_name=test_name
    )
    deliver_test_report_files(
        report_files_mapping=report_files_mapping,
        output_directory=output_directory_path
    )


def create_report_files(
    log_string: str,
    validity_df: DataFrame,
    test_name: str,
    event_id_job_id_map: dict[str, str] | None = None
) -> dict[str, str | DataFrame]:
    """Method to create report files from logs and validity dataframe

    :param log_string: String representing the log files
    :type log_string: `str`
    :param validity_df: :class:`DataFrame` holding the information on the test
    files
    :type validity_df: :class:`DataFrame`
    :param test_name: The test name (or prefix) to give to the report files
    :type test_name: `str`
    """
    results_df = logs_validity_df_to_results(
        log_string=log_string,
        validity_df=validity_df,
        event_id_job_id_map=event_id_job_id_map
    )
    report_files_mapping = get_report_files_mapping_from_dataframe_report(
        results_df=results_df,
        results_prefix=test_name
    )
    return report_files_mapping
