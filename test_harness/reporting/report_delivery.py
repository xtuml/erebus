"""Methods for delivering test report files
"""
import os
from pandas import DataFrame


def deliver_test_report_files(
    report_files_mapping: dict[str, str | DataFrame],
    output_directory: str
) -> None:
    """Method to save files (mapped to file names) into an output directory.
    If the output directory does not exist it is created

    :param report_files_mapping: Dictionary mapping file name to file
    :type report_files_mapping: `dict`[`str`, `str`  |  :class:`DataFrame`]
    :param output_directory: The path to the output directory
    :type output_directory: `str`
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory, exist_ok=True)
    for report_file_name, report_file in report_files_mapping.items():
        deliver_test_report_file(
            report_file_name,
            report_file,
            output_directory
        )


def deliver_test_report_file(
    report_file_name: str,
    report_file: str | DataFrame,
    output_directory: str
) -> None:
    """Method to save a report file given its name and an output directory to
    save it in

    :param report_file_name: The name given to the report file
    :type report_file_name: `str`
    :param report_file: The report file
    :type report_file: `str` | :class:`DataFrame`
    :param output_directory: The path to the output directory
    :type output_directory: `str`
    :raises RuntimeError: Raises a :class:`RuntimeError` if the output
    directory does not exist
    """
    if not os.path.exists(output_directory):
        raise RuntimeError(f"The directory {output_directory} does not exist")
    out_path = os.path.join(output_directory, report_file_name)
    if isinstance(report_file, DataFrame):
        report_file.to_csv(out_path, index=True)
    else:
        with open(out_path, 'w', encoding="utf-8") as file:
            file.write(report_file)
