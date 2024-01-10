"""Module for abstracting the results of a test run."""

from abc import ABC, abstractmethod
from typing import Iterator, Any, TypedDict, Literal, Iterable

# from threading import Thread, Lock
# import time

import pandas as pd
import sqlalchemy as sa
import dask.dataframe as dd


class ResultsHolder(ABC):
    """Abstract base class for a results holder."""
    @abstractmethod
    def values(self) -> Iterator[dict[str, Any]]:
        """Return the values of the results as a dictionary."""
        pass

    @abstractmethod
    def keys(self) -> Iterator[str]:
        """Return the keys of the results as a dictionary."""
        pass

    def items(self) -> Iterable[tuple[str, dict[str, Any]]]:
        """Return the keys and values of the results as a dictionary."""
        key_iterator = self.keys()
        values_iterator = self.values()
        while True:
            try:
                key = next(key_iterator)
                values = next(values_iterator)
                yield key, values
            except StopIteration:
                break

    @abstractmethod
    def __getitem__(self, key: str) -> dict[str, Any]:
        """Return the value of the result with the given key."""
        pass

    @abstractmethod
    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        """Set the value of the result with the given key."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of results."""
        pass

    @abstractmethod
    def __contains__(self, key: str) -> bool:
        """Return whether the results contain the given key."""
        pass

    @abstractmethod
    def filter_rows_on_field_value(self, field: str, value: Any) -> None:
        """Remove rows where the given field has the given value."""
        pass

    @abstractmethod
    def to_pandas(self) -> pd.DataFrame:
        """Return the results as a pandas dataframe."""
        pass

    @abstractmethod
    def to_dask(self) -> dd.DataFrame:
        """Return the results as a dask dataframe."""
        pass


class DictResultsHolder(ResultsHolder):
    """A results holder that stores results in a dictionary."""

    def __init__(
        self,
        fields: list[str] = None,
    ) -> None:
        """Constructor method"""
        self._results: dict[str, dict[str, Any]] = {}
        self._fields = fields

    def values(self) -> Iterator[dict[str, Any]]:
        """Return the values of the results as a dictionary."""
        return iter(self._results.values())

    def keys(self) -> Iterator[str]:
        """Return the keys of the results as a dictionary."""
        return iter(self._results.keys())

    def __getitem__(self, key: str) -> dict[str, Any]:
        """Return the value of the result with the given key."""
        return self._results[key]

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        """Set the value of the result with the given key."""
        if key not in self._results:
            self._results[key] = {}
        self._results[key] = {**self._results[key], **value}

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self._results)

    def __contains__(self, key: str) -> bool:
        """Return whether the results contain the given key."""
        return key in self._results

    def filter_rows_on_field_value(self, field: str, value: Any) -> None:
        """Remove rows where the given field has the given value."""
        self._results = {
            key: row
            for key, row in self._results.items()
            if field in row
            if row[field] != value
        }

    def to_pandas(self) -> pd.DataFrame:
        """Return the results as a pandas dataframe."""
        if self._fields is None:
            return pd.DataFrame.from_dict(self._results, orient="index")
        else:
            return pd.DataFrame.from_dict(
                self._results,
                orient="index",
                columns=self._fields,
            )
        # return pd.DataFrame.from_dict(self._results, orient="index")

    def to_dask(self) -> dd.DataFrame:
        """Return the results as a dask dataframe."""
        return dd.from_pandas(self.to_pandas(), npartitions=1)


class PandasResultsHolder(ResultsHolder):
    """A results holder that stores results in a pandas dataframe."""

    def __init__(self) -> None:
        """Constructor method"""
        self._results: pd.DataFrame = pd.DataFrame()

    def values(self) -> Iterator[dict[str, Any]]:
        """Return the values of the results as a dictionary."""
        return iter(self._results.to_dict("records"))

    def keys(self) -> Iterator[str]:
        """Return the keys of the results as a dictionary."""
        return iter(self._results.index)

    def __getitem__(self, key: str) -> dict[str, Any]:
        """Return the value of the result with the given key."""
        return self._results[key].to_dict()

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        """Set the value of the result with the given key."""
        for col, col_value in value.items():
            self._results.loc[key, col] = col_value

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self._results)

    def __contains__(self, key: str) -> bool:
        """Return whether the results contain the given key."""
        return key in self._results.index

    def filter_rows_on_field_value(self, field: str, value: Any) -> None:
        """Remove rows where the given field has the given value."""
        self._results = self._results[self._results[field] != value]

    def to_pandas(self) -> pd.DataFrame:
        """Return the results as a pandas dataframe."""
        return self._results

    def to_dask(self) -> dd.DataFrame:
        """Return the results as a dask dataframe."""
        return dd.from_pandas(self._results, npartitions=1)


class SQLAlchemyTableColumn(TypedDict):
    """A type for the columns of a SQLAlchemy table"""

    name: str
    type_: Literal["float", "string", "integer"]
    primary_key: bool


col_type_map = {
    "float": sa.Float,
    "string": sa.String,
    "integer": sa.Integer,
}

"""Removed until I can figure out how to make it work with SQLAlchemy.
"""

# TODO: Make this work and implement it in the test harness.
# class DataBaseTableResultsHolder(ResultsHolder):
#     """A results holder that stores results in a database table."""

#     def __init__(
#         self,
#         db_path: str,
#         primary_key: SQLAlchemyTableColumn,
#         table_columns: list[SQLAlchemyTableColumn],
#     ) -> None:
#         """Constructor method"""
#         engine = sa.create_engine(db_path)
#         metadata = sa.MetaData()
#         self._primary_key = primary_key
#         self._table_columns = table_columns
#         self._tables = {
#             table["name"]: sa.Table(
#                 table["name"],
#                 metadata,
#                 *[
#                     sa.Column(
#                         col["name"],
#                         col_type_map[col["type_"]],
#                         primary_key=col["primary_key"],
#                     )
#                     for col in [primary_key, table]
#                 ],
#             )
#             for table in table_columns
#         }
#         # table = sa.Table(
#         #     "results",
#         #     metadata,
#         #     *[
#         #         sa.Column(
#         #             col["name"],
#         #             col_type_map[col["type_"]],
#         #             primary_key=col["primary_key"],
#         #         )
#         #         for col in columns
#         #     ],
#         # )
#         metadata.create_all(engine)
#         # self._table = table
#         self._engine = engine
#         # self._primary_key_column = self._table.primary_key.columns[0]
#         # self._table.columns.keys()
#         self._thread = Thread(target=self._commit_on_length, daemon=True)
#         self._lock = Lock()
#         self._keep_committing = True
#         self._batch_results = {
#             table["name"]: {"batch": DictResultsHolder(), "lock": Lock()}
#             for table in self._table_columns
#         }
#         self._full_table: sa.Table | None = None

#     def start_committing(self) -> None:
#         """Start a thread to commit results to the database."""
#         self._thread.start()

#     def stop_committing(self) -> None:
#         """Stop the thread that commits results to the database."""
#         self._keep_committing = False
#         self._thread.join()

#     def join_tables(self) -> None:
#         """Join the tables in the database."""
#         if self._thread.is_alive():
#             raise RuntimeError("Cannot be used when commiting to database.")
#         self._full_table = sa.join(
#             *[table for table in self._tables.values()]
#         )

#     def _commit_on_length(self) -> None:
#         while self._keep_committing:
#             time.sleep(60)
#             for name, batch_lock in self._batch_results.items():
#                 with batch_lock["lock"]:
#                     if len(batch_lock["batch"]) > 100000:
#                         self._insert_batch_results(name)
#         for name, batch_lock in self._batch_results.items():
#             with batch_lock["lock"]:
#                 self._insert_batch_results(name)

#     def _insert_batch_results(self, name, batch) -> None:
#         """Insert a batch of entries from self._batch_results_holder into
#         the database."""
#         insert_stmt = (
#             self._tables[name]
#             .insert()
#             .values(
#                 list(
#                     {self._primary_key["name"]: key, **value}
#                     for key, value in self._batch_results[name].items()
#                 )
#             )
#         )
#         self._engine.execute(insert_stmt)
#         self._batch_results[name]["batch"] = DictResultsHolder()

#     def values(self) -> Iterator[dict[str, Any]]:
#         """Return the values of the results as a dictionary."""
#         if self._thread.is_alive():
#             raise RuntimeError(
#                 "Cannot iterate over results while committing to database."
#             )
#         select_stmt = sa.select([self._full_table])
#         result = self._engine.execute(select_stmt)
#         for row in result:
#             yield dict(row)

#     def keys(self) -> Iterator[str]:
#         """Return the keys of the results as a dictionary."""
#         if self._thread.is_alive():
#             raise RuntimeError(
#                 "Cannot iterate over results while committing to database."
#             )
#         select_stmt = sa.select([self._full_table.primary_key.columns[0]])
#         result = self._engine.execute(select_stmt)
#         for row in result:
#             yield row[0]

#     def __getitem__(self, key: str) -> dict[str, Any]:
#         """Return the value of the result with the given key."""
#         if self._thread.is_alive():
#             raise RuntimeError("Cannot be used when commiting to database.")
#         result = self._get_row_by_key(key)
#         if result is None:
#             raise KeyError(f"Key '{key}' not found in results.")
#         return {
#             col: result[col]
#             for col in self._full_table.columns.keys()
#             if col != self._primary_key["name"] and result[col] is not None
#         }

#     def __setitem__(self, key: str, value: dict[str, Any]) -> None:
#         """Set the value of the result with the given key."""
#         for field, field_value in value.items():
#             batch_lock = self._batch_results[field]
#             with batch_lock["lock"]:
#                 batch_lock["batch"][key] = {field: field_value}
#             # if self._get_row_by_key(key):
#             #     self._create_row(key)
#             # if len(value) == 0:
#             #     return
#             # stmnt = sa.update(self._table).where(
#             #     self._primary_key_column == key
#             # ).values(**value)
#             # self._engine.execute(stmnt)

#     def __len__(self) -> int:
#         """Return the number of results."""
#         if self._thread.is_alive():
#             raise RuntimeError("Cannot be used when commiting to database.")
#         select_stmt = sa.select([sa.func.count()]).select_from(
#             self._tables[self._table_columns[0]["name"]]
#         )
#         result = self._engine.execute(select_stmt)
#         return result.fetchone()[0]

#     def __contains__(self, key: str) -> bool:
#         """Return whether the results contain the given key."""
#         return self._get_row_by_key(key) is not None

#     # def _create_row(self, key: str) -> None:
#     #     stmnt = sa.insert(self._table).values(
#     #         {self._primary_key["name"]: key}
#     #     )
#     #     self._engine.execute(stmnt)
#     #     self._engine.commit()

#     def _get_row_by_key(self, key: str):
#         stmt = sa.select(self._tables[self._table_columns[0]["name"]]).where(
#             self._tables[self._table_columns[0]["name"]].primary_key.columns[0]
#             == key
#         )
#         result = self._engine.execute(stmt)
#         return result.fetchone()

#     def filter_rows_on_field_value(self, field: str, value: Any) -> None:
#         """Remove rows where the given field has the given value."""
#         stmt = sa.delete(self._full_table).where(
#             self._full_table.c[field] == value
#         )
#         self._engine.execute(stmt)

#     def to_pandas(self) -> pd.DataFrame:
#         """Return the results as a pandas dataframe."""
#         return pd.read_sql_table("results", self._engine)

#     def to_dask(self) -> dd.DataFrame:
#         """Return the results as a dask dataframe."""
#         return dd.read_sql_table("results", self._engine)
