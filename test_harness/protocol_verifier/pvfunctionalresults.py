# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
import pandas as pd

from .pvresults import PVResults


class PVFunctionalResults(PVResults):
    """Sub-class of :class:`PVResults` to update and store functional results
    within a Functional test run
    """

    def __init__(
        self,
    ) -> None:
        """Constructor method"""
        super().__init__()
        self.job_ids = []
        self.jobs_info = []
        self.file_names = []
        self.responses = []

    def update_from_sim(
        self,
        job_id: str,
        file_name: str,
        job_info: dict[str, str],
        response: str,
        **kwargs
    ) -> None:
        """Implementation of abstract method when given a data point from the
        Functional simulaiona

        :param job_id: The unique id of the job
        :type job_id: `str`
        :param file_name: The name of the output file the test file has been
        saved as.
        :type file_name: `str`
        :param job_info: The validity information related to the job
        :type job_info: `dict`[`str`, `str`]
        :param response: Th response received from the http intermediary
        :type response: `str`
        """
        self.update_test_files_info(
            job_ids=[job_id], jobs_info=[job_info], file_names=[file_name]
        )
        self.update_responses([response])

    def update_test_files_info(
        self,
        job_ids: list[str],
        jobs_info: list[dict[str, str]],
        file_names: list[str],
    ) -> None:
        """Method to update the test files info for the results.
        The lists should be of the same legnth and every index of each list
        should refer to the same file

        :param job_ids: List of job ids
        :type job_ids: `list`[`str`]
        :param jobs_info: List of dictionary mapping name of info to info
        :type jobs_info: `list`[`dict`[`str`, `str`]]
        :param file_names: List of file names of the tests
        :type file_names: `list`[`str`]
        :raises RuntimeError: Raises a :class:`RuntimeError` if the lists are
        not all of the same length
        """
        if (
            len(
                set(
                    len(obj_list)
                    for obj_list in [job_ids, jobs_info, file_names]
                )
            )
            != 1
        ):
            raise RuntimeError("all lists should be the same length")
        self.job_ids.extend(job_ids)
        self.jobs_info.extend(jobs_info)
        self.file_names.extend(file_names)

    def update_responses(self, responses: list[str]) -> None:
        """Method to update the responses

        :param response: List of responses
        :type response: `str`
        """
        self.responses.extend(responses)

    def create_validity_dataframe(self) -> pd.DataFrame:
        """Create a validity dataframe for the instance

        :return: Returns the validity dataframe
        :rtype: :class:`pd`.`DataFrame`
        """
        validity_df_lines = [
            {**{"JobId": job_id, "FileName": file_name}, **job_info}
            for job_id, job_info, file_name in zip(
                self.job_ids, self.jobs_info, self.file_names
            )
        ]
        validity_df = pd.DataFrame.from_records(validity_df_lines)
        validity_df.set_index("JobId", inplace=True)
        return validity_df
