"""Script to create a Test Harness template event from a PV event sequence.

Usage:
    python create_test_file_json.py <filename> [-t <sequence_type>] \
        [-v <validity>] [-o <outfile>]
"""
from typing import Any
import json

import argparse

parser = argparse.ArgumentParser(
    prog="TestHarnessEventDataCreator",
    description=(
        "Takes a PV event sequence json list and formats it "
        "such that it is ingestible by the Test Harness as template"
        " test data."
    )
)

parser.add_argument(
    'filename',
    type=str,
    help="The path of the file to generate test harness template data from"
)
parser.add_argument(
    "-t",
    "--sequencetype",
    default="ValidSols",
    type=str,
    help='Optional argument to add the Category of the template file'
)
parser.add_argument(
    "-v",
    "--validity",
    default="valid",
    type=str,
    choices=["valid", "invalid"],
    help=(
        'Optional argument to specifiy the validity of the template file.'
        'Can only use "valid" or "invalid" as values.'
    )
)
parser.add_argument(
    "-o",
    "--outfile",
    type=str,
    default=None,
    help='Optional argument to output to specified filename'
)


def main() -> None:
    """Main method to run the script
    """
    args = parser.parse_args()
    file_name: str = args.filename
    with open(file_name, 'r', encoding="utf8") as input_file:
        event_sequence = json.load(input_file)
    validity = True if args.validity == "valid" else False
    sequence_type = args.sequencetype
    output_file_path = (
        args.outfile
        if args.outfile
        else file_name.replace(".json", "") + "_test_harness_temp.json"
    )
    job_names = get_job_names_string(event_sequence)
    test_harness_event_template = create_test_harness_template_event(
        job_file=event_sequence,
        job_name=job_names,
        sequence_type=sequence_type,
        validity=validity
    )
    with open(output_file_path, 'w', encoding="utf8") as out_file:
        json.dump(
            test_harness_event_template,
            out_file,
            indent=4
        )


def get_job_names_string(event_sequence: list[dict]) -> str:
    """Method to get the job names string from the event sequence

    :param event_sequence: The event sequence
    :type event_sequence: `list`[`dict`]
    :return: Returns the job names string
    :rtype: `str`
    """
    job_names = set()
    for event in event_sequence:
        job_names.add(event["jobName"])
    return " + ".join(job_names)


def create_test_harness_template_event(
    job_file: list[dict],
    job_name: str,
    sequence_type: str,
    validity: bool
) -> dict[str, Any]:
    """Method to create a test harness template event

    :param job_file: The job file
    :type job_file: `list`[`dict`]
    :param job_name: The job name
    :type job_name: `str`
    :param sequence_type: The sequence type
    :type sequence_type: `str`
    :param validity: The validity
    :type validity: `bool`
    :return: Returns the test harness template event
    :rtype: `dict`[`str`, `Any`]
    """
    return {
        "job_file": job_file,
        "job_name": job_name,
        "sequence_type": sequence_type,
        "validity": validity
    }


if __name__ == "__main__":
    main()
