# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
from abc import ABC, abstractmethod
from datetime import datetime


class PVResults(ABC):
    """Base abstract class to hold an calculate results from a PV simulation"""

    def __init__(self) -> None:
        """Constructor method"""
        self.time_start = None

    @property
    def time_start(self) -> datetime | None:
        """Property getter for the start time of the simulation

        :return: Returns the start time if set
        :rtype: :class:`datetime` | `None`
        """
        return self._time_start

    @time_start.setter
    def time_start(self, input_time_start: datetime | None) -> None:
        """Property setter for the start time of the simulation

        :param input_time_start: The start time
        :type input_time_start: :class:`datetime` | `None`
        """
        self._time_start = input_time_start

    @abstractmethod
    def update_from_sim(
        self,
        *,
        event_list: list[dict],
        job_id: str,
        response: str,
        time_completed: datetime,
        file_name: str,
        job_info: dict[str, str],
    ) -> None:
        """Abstract method used to do an update when receiving data output
        from the simulation

        :param event_list: The list of event dicts
        :type event_list: `list`[`dict`]
        :param job_id: The job id the lit of events are associated with
        :type job_id: `str`
        :param file_name: The name of the file that was sent and/or saved
        :type file_name: `str`
        :param job_info: The validity information pertaining to the job
        :type job_info: `dict`[`str`, `str`]
        :param response: The response received from the http request sending
        the file
        :type response: `str``
        :param time_completed: The time the request was completed at
        :type time_completed: :class:`datetime`
        """
