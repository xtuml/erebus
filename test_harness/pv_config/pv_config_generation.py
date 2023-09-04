"""Generate Protocol Verifier config using Plus2Json
"""
import zipimport
import logging
import json

import xtuml

from test_harness.utils import (
    FilterException,
    ErrorFilter,
    collect_error_logs_from_func
)

# import plus2json
importer = zipimport.zipimporter("test_harness/plus2json.pyz")
plus2json = importer.load_module('plusj2son.plus2json')


class Plus2JsonString(plus2json.plus2json.Plus2Json):
    """Subclass of Plus2Json needed to integrate with Test Harness correctly
    """
    def __init__(self) -> None:
        super().__init__()

    def check_consistency(self) -> None:
        """Method to check whether the model from puml file works correctly

        :raises RuntimeError: Raises a :class:`RuntimeError` when there is an
        error with the model
        """
        if (
            xtuml.check_association_integrity(self.metamodel)
            + xtuml.check_uniqueness_constraint(self.metamodel)
        ) > 0:
            logging.getLogger().error('Failed model integrity check')
            raise RuntimeError("Check of puml failed whilst loading job defs")

    def get_job_def_strings(self, file_names: list[str]) -> list[str]:
        """Method to obtain job def strings from a list of input puml
        graphical job definitions

        :param file_names: List of puml file paths
        :type file_names: `list`[`str`]
        :raises RuntimeError: Raises a :class:`RuntimeError` when there is an
        error in the puml file syntax
        :return: Returns a list of the job definition json strings
        :rtype: `list`[`str`]
        """
        self.filename_input(file_names)
        plus2json_log_filter = ErrorFilter()
        try:
            collect_error_logs_from_func(
                logger=plus2json.populate.logger,
                filter=plus2json_log_filter,
                func=self.load,
                opts={"event_data": []}
            )
        except FilterException:
            raise RuntimeError(
                f"Plus2json found the following errors that should be "
                f"rectified:\n{plus2json_log_filter.output_error_message}"
            )

        # self.load(opts={"event_data": []})
        # output each job definition
        return [
            json.dumps(
                plus2json.definition.JobDefn_json(job_defn),
                indent=4,
                separators=(',', ': ')
            )
            for job_defn in self.metamodel.select_many('JobDefn')
        ]


def get_job_defs_from_uml_files(
    uml_file_paths: list[str]
) -> list[str]:
    """Method to obtain job def strings from a list of input puml
    graphical job definitions using :class:`Plus2JsonString`

    :param uml_file_paths: _description_
    :type uml_file_paths: list[str]
    :return: _description_
    :rtype: list[str]
    """
    plus2json_handler = Plus2JsonString()
    return plus2json_handler.get_job_def_strings(
        uml_file_paths
    )
