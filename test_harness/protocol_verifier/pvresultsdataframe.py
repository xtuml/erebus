# pylint: disable=R0902
# pylint: disable=R0913
# pylint: disable=W0221
# pylint: disable=W0246
# pylint: disable=W0613
# pylint: disable=C0302
# pylint: disable=C0114
# pylint: disable=C0103
# pylint: disable=R0914
import warnings

from .pvperformanceresults import (
    PVPerformanceResults,
)


class PVResultsDataFrame(PVPerformanceResults):
    """Sub class of :class:`PVPerformanceResults: to get perfromance results
    using a pandas dataframe as the results holder.
    """

    def __init__(self, binning_window: int = 1) -> None:
        """Constructor method"""
        warnings.warn(
            (
                "PVResultsDataFrame will soon be deleted and replaced with a"
                " different paradigm using PVResultsDataFrameCalculator."
            ),
            DeprecationWarning,
        )
        super().__init__(binning_window)
