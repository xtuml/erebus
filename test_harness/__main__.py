"""Main function to call test harness
"""
import argparse

from test_harness.run_app import main

parser = argparse.ArgumentParser(
    prog="test harness"
)

parser.add_argument(
    '-o', '--outdir', metavar='dir',
    help="Path to output directory",
    default=None,
    dest="test_output_directory"
)
parser.add_argument(
    '--harness-config',
    help="Path to harness configuration",
    default=None,
    dest="harness_config_path"
)

parser.add_argument(
    '--test-config',
    help="Path to test configuration yaml file",
    default=None,
    dest="test_config_yaml_path"
)

parser.add_argument(
    'puml_file_paths', nargs='*', help='Input .puml files',
)


if __name__ == "__main__":
    args: argparse.Namespace = parser.parse_args()
    main(**vars(args))
