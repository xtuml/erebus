# pylint: disable=R0913
"""
Creates the test harness app
"""
import os
from typing import Mapping, Optional, Callable, Union, Any, Generator
from uuid import uuid4
from ctypes import c_int, c_bool
from contextlib import contextmanager
import traceback

from flask import Flask, request, make_response, Response, jsonify
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest
from tqdm import tqdm

from test_harness.config.config import HarnessConfig, TestConfig
from multiprocessing import Value


class HarnessApp(Flask):
    """Subclass of :class:`Flask` needed to provide
    config to route methods

    :param import_name: See :class:`Flask` documenation
    :type import_name: str
    :param harness_config_path: Path of the harness config, defaults to None
    :type harness_config_path: Optional[str], optional
    :param static_url_path: See :class:`Flask` documentation, defaults to None
    :type static_url_path: Optional[str], optional
    :param static_folder: See :class:`Flask` documentation,
    defaults to "static"
    :type static_folder: Optional[Union[str, os.PathLike]], optional
    :param static_host: See :class:`Flask` documentation, defaults to None
    :type static_host: Optional[str], optional
    :param host_matching: See :class:`Flask` documentation, defaults to False
    :type host_matching: bool, optional
    :param subdomain_matching: See :class:`Flask` documentation,
    defaults to False
    :type subdomain_matching: bool, optional
    :param template_folder: See :class:`Flask` documentation,
    defaults to "templates"
    :type template_folder: Optional[Union[str, os.PathLike]], optional
    :param instance_path: See :class:`Flask` documentation, defaults to None
    :type instance_path: Optional[str], optional
    :param instance_relative_config: See :class:`Flask` documentation,
    defaults to False
    :type instance_relative_config: bool, optional
    :param root_path: See :class:`Flask` documentation, defaults to None
    :type root_path: Optional[str], optional
    :ivar harness_config: Instance of HarnessConfig
    :vartype harness_config: :class:`HarnessConfig`
    :ivar harness_progress_manager: Instance of TestHarnessProgessManager
    :vartype harness_progress_manager: :class:`TestHarnessProgessManager`
    """

    def __init__(
        self,
        import_name: str,
        harness_config_path: Optional[str] = None,
        static_url_path: Optional[str] = None,
        static_folder: Optional[Union[str, os.PathLike]] = "static",
        static_host: Optional[str] = None,
        host_matching: bool = False,
        subdomain_matching: bool = False,
        template_folder: Optional[Union[str, os.PathLike]] = "templates",
        instance_path: Optional[str] = None,
        instance_relative_config: bool = False,
        root_path: Optional[str] = None,
    ) -> None:
        """Constructor method"""
        self.harness_config = HarnessConfig(config_path=harness_config_path)
        self.harness_progress_manager = TestHarnessProgessManager()
        super().__init__(
            import_name,
            static_url_path,
            static_folder,
            static_host,
            host_matching,
            subdomain_matching,
            template_folder,
            instance_path,
            instance_relative_config,
            root_path,
        )
        self.test_to_run = {}

    def handle_multipart_file_upload(
        self,
        save_file_dir_path: str,
        file_handler: Callable[[list[FileStorage]], Response],
    ) -> Response:
        """Function to handle the upload of files

        :param save_file_dir_path: The path to save the file to
        :type save_file_dir_path: `str`
        :return: Return the response
        :rtype: :class:`Response`
        """
        # requests must be of type multipart/form-data
        if request.mimetype != "multipart/form-data":
            return make_response(
                "mime-type must be multipart/form-data\n", 400
            )
        # get files
        uploaded_files: list[FileStorage] = [
            request.files[uploaded_file_identifier]
            for uploaded_file_identifier in request.files
        ]
        # get filenames
        uploaded_files_names = list(map(lambda x: x.filename, uploaded_files))

        # check for files without file name
        if any(
            uploaded_file_name == ""
            for uploaded_file_name in uploaded_files_names
        ):
            return make_response(
                "One of the uploaded files has no filename\n", 400
            )

        # check if some of the files have the same name
        if len(set(uploaded_files_names)) < len(uploaded_files_names):
            return make_response(
                "At least two of the uploaded files share the same filename\n",
                400,
            )
        response = file_handler(uploaded_files, save_file_dir_path)
        return response

    def upload_uml_files(self) -> Response:
        """Function to handle the upload of UML files

        :return: 200 response if files uploaded successfully and
        400 if unsuccessful
        :rtype: :class:`Response`
        """
        return self.handle_multipart_file_upload(
            save_file_dir_path=self.harness_config.uml_file_store,
            file_handler=handle_multiple_file_uploads,
        )

    def upload_test_files(self) -> Response:
        """Function to handle the upload of test files to test file store

        :return: 200 response if files uploaded successfully and
        400 if unsuccessful
        :rtype: :class:`Response`
        """
        return self.handle_multipart_file_upload(
            save_file_dir_path=self.harness_config.test_file_store,
            file_handler=handle_multiple_file_uploads,
        )

    def upload_profile(self) -> Response:
        """Function to handle the upload of a profile file

        :return: 200 response if file uploaded successfully and
        400 if unsuccessful
        :rtype: :class:`Response`
        """
        return self.handle_multipart_file_upload(
            save_file_dir_path=self.harness_config.profile_store,
            file_handler=handle_single_file_upload,
        )

    def start_test(self) -> Response:
        """Function to handle starting a test"""
        try:
            json_dict = request.get_json()
            success, json_response = self.handle_start_test_json_request(
                json_dict
            )
            return jsonify(json_response), 200 if success else 400
        except BadRequest as error:
            return error.get_response()

    def test_is_running(self) -> Response:
        """
        Function to handle checking if a test is running.

        Returns:
            A Flask response indicating whether a test is running and if so,
            the percentage of completion.
        """
        if self.harness_progress_manager.test_is_running.value:
            percentage_done = (
                self.harness_progress_manager.get_progress_percentage()
            )
            returnVal: Flask.response_class = (
                jsonify(
                    {
                        "running": True,
                        "details": {"percent_done": f"{percentage_done:.2f}"},
                    }
                ),
                200,
            )
            return returnVal
        return jsonify({"running": False}), 200

    def handle_start_test_json_request(
        self, request_json: dict
    ) -> tuple[bool, dict[str, dict[str, Any]]]:
        """_summary_

        :param request_json: The request json sent as a python dictionary
        :type request_json: `dict`
        :return: Returns a tuple with:
        * a boolean indicating if the request json is valid
        * a response dictionary indicating the test config used and the
        location of the output files
        :rtype: `tuple`[`bool`, `dict`[`str`, `dict`[`str`, `Any`]]]
        """
        test_to_run = {}
        unknown_keys = set(request_json.keys()).difference(
            self.valid_json_dict_keys
        )
        if unknown_keys:
            return (
                False,
                {
                    "Error": (
                        f"The following fields: {','.join(unknown_keys)}"
                        "are not valid fields to use."
                    )
                },
            )
        response_json = {}
        for key in self.valid_json_dict_keys:
            if key == "TestName":
                test_name = request_json[key] if key in request_json else None
                test_name, test_output_directory = (
                    create_test_output_directory(
                        harness_config=self.harness_config, test_name=test_name
                    )
                )
                test_to_run["TestOutputDirectory"] = test_output_directory
                response_json["TestOutputFolder"] = (
                    f"Tests under name {test_name} in the directory"
                    f"{test_output_directory}"
                )
            else:
                test_config = TestConfig()
                if key in request_json:
                    test_config.parse_from_dict(request_json[key])
                test_to_run["TestConfig"] = test_config
                response_json["TestConfig"] = test_config.config_to_dict()
        self.test_to_run = test_to_run
        return (True, response_json)

    @property
    def test_to_run(self) -> dict | None:
        """Property providing the most recent test to run

        :return: Returns the test to run property
        :rtype: `dict` | `None`
        """
        return self._test_to_run

    @test_to_run.setter
    def test_to_run(self, test_to_run_mapping: dict | None) -> None:
        """Setter for test_to_run

        :param test_to_run_mapping: Dictionary for the test to run
        :type test_to_run_mapping: `dict` | `None`
        """
        self._test_to_run = test_to_run_mapping

    @property
    def valid_json_dict_keys(self) -> set[str]:
        """Property returning the valid json keys

        :return: Returns a set of the keys
        :rtype: `set`[`str`]
        """
        return {"TestConfig", "TestName"}


def create_app(
    harness_config_path: Optional[str] = None,
    test_config: Optional[Mapping] = None,
) -> HarnessApp:
    """Creates HarnessApp(Flask)

    :param harness_config_path: _description_, defaults to None
    :type harness_config_path: Optional[str], optional
    :param test_config: Configuration test config, defaults to None
    :type test_config: :class:`Mapping`, optional
    :return: Returns a HarnessApp instance
    :rtype: :class:`HarnessApp`
    """
    # create and configure the app
    app = HarnessApp(
        __name__,
        harness_config_path=harness_config_path,
        instance_relative_config=True,
    )
    app.config.from_mapping()

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # route to upload uml
    wrap_function_app(app.upload_uml_files, "/uploadUML", ["POST"], app)

    # route to upload profile
    @app.route("/upload/profile", methods=["POST"])
    def upload_profile() -> None:
        return app.upload_profile()

    # route to upload profile
    @app.route("/upload/test-files", methods=["POST"])
    def upload_test_files() -> None:
        return app.upload_test_files()

    # route to start
    @app.route("/startTest", methods=["POST"])
    def start_test() -> None:
        return app.start_test()

    @app.route("/isTestRunning", methods=["GET"])
    def test_is_running() -> None:
        return app.test_is_running()

    return app


def handle_single_file_upload(
    uploaded_files: list[FileStorage], save_file_dir_path: str
) -> Response:
    """Handler for a single file upload using multipart

    :param uploaded_files: The list of files uploaded
    :type uploaded_files: `list`[:class:`FileStorage`]
    :param save_file_dir_path: The path of the directory to save files to
    :type save_file_dir_path: `str`
    :return: Rerturns a response
    :rtype: :class:`Response`
    """
    if len(uploaded_files) > 1:
        return make_response(
            "More than two files uploaded. A single file is required\n", 400
        )
    return handle_multiple_file_uploads(uploaded_files, save_file_dir_path)


def handle_multiple_file_uploads(
    uploaded_files: list[FileStorage], save_file_dir_path: str
) -> Response:
    """Handler for a multiple file uploads using multipart

    :param uploaded_files: The list of files uploaded
    :type uploaded_files: `list`[:class:`FileStorage`]
    :param save_file_dir_path: The path of the directory to save files to
    :type save_file_dir_path: `str`
    :return: Rerturns a response
    :rtype: :class:`Response`
    """
    for uploaded_file in uploaded_files:
        handle_uploaded_file(uploaded_file, save_file_dir_path)
    return make_response("Files uploaded successfully\n", 200)


def handle_uploaded_file(file: FileStorage, save_file_dir_path: str) -> None:
    """Helper function to create output path and save uploaded file

    :param file: FileStroage class containing the uploaded file
    and metadata
    :type file: class:`FileStorage`
    :param save_file_dir_path: Path of folder to save the file in
    :type save_file_dir_path: str
    """
    out_file_path = os.path.join(save_file_dir_path, file.filename)
    file.save(out_file_path)


def wrap_function_app(
    func_to_wrap: Callable, route: str, methods: list[str], app: Flask
) -> Callable[[], Response]:
    """Wraps a function in a Flask app route

    :param func_to_wrap: The function to wrap
    :type func_to_wrap: `Callable`
    :param route: The endpoint of the route
    :type route: `str`
    :param methods: The method/s of the endpoint
    :type methods: `list`[`str`]
    :param app: The Flask app
    :type app: :class:`Flask`
    :return: The app.route decorated function
    :rtype: `Callable`[[], :class:`Response`]
    """

    @app.route(route, methods=methods)
    def wrapped_function() -> Response:
        return func_to_wrap()

    return wrapped_function


def create_test_output_directory(
    harness_config: HarnessConfig, test_name: str | None = None
) -> tuple[str, str]:
    """Method to create a test output directory given harness config and a
    test name. If no test name is given a uuid is given to the test and
    returned along with the directory path

    :param harness_config: The config for the test harness
    :type harness_config: :class:`HarnessConfig`
    :param test_name: The identifier for the test, defaults to `None`
    :type test_name: `str` | `None`, optional
    :return: Returns a tuple of:
    * the test name
    * the path to the directory for the test
    :rtype: `tuple`[`str`, `str`]
    """
    if not test_name:
        test_name = str(uuid4())
    test_output_directory_path = os.path.join(
        harness_config.report_file_store, test_name
    )
    if not os.path.exists(test_output_directory_path):
        os.makedirs(test_output_directory_path)
    return (test_name, test_output_directory_path)


class TestHarnessPbar(tqdm):
    """Subclass of tqdm to handle updating the progress bar

    :param args: Positional arguments to be passed to the parent class
    :type args: `tuple`
    :param kwargs: Keyword arguments to be passed to the parent class
    :type kwargs: `dict`
    """

    def __init__(
        self,
        iterable=None,
        desc=None,
        total=None,
        leave=True,
        file=None,
        ncols=None,
        mininterval=0.1,
        maxinterval=10.0,
        miniters=None,
        ascii=None,
        disable=False,
        unit="it",
        unit_scale=False,
        dynamic_ncols=False,
        smoothing=0.3,
        bar_format=None,
        initial=0,
        position=None,
        postfix=None,
        unit_divisor=1000,
        write_bytes=False,
        lock_args=None,
        nrows=None,
        colour=None,
        delay=0,
        gui=False,
        **kwargs,
    ):
        """Constructor method"""
        self.th_progress = Value(c_int, 0)
        super().__init__(
            iterable,
            desc,
            total,
            leave,
            file,
            ncols,
            mininterval,
            maxinterval,
            miniters,
            ascii,
            disable,
            unit,
            unit_scale,
            dynamic_ncols,
            smoothing,
            bar_format,
            initial,
            position,
            postfix,
            unit_divisor,
            write_bytes,
            lock_args,
            nrows,
            colour,
            delay,
            gui,
            **kwargs,
        )

    def update(self, n: int = 1) -> None:
        """Method to update the progress bar

        :param n: The number of steps to update the progress bar by,
        defaults to 1
        :type n: `int`, optional
        """
        super().update(n)
        self.th_progress.value += n

    def get_th_progress(self) -> int:
        """Method to get the progress of the progress bar

        :return: Returns the progress of the progress bar
        :rtype: `int`
        """
        return self.th_progress.value


class TestHarnessProgessManager:
    """Class to manage the progress of the test harness"""

    def __init__(self) -> None:
        """Constructor method"""
        self.test_is_running = Value(c_bool, False)
        self.pbars: dict[str, TestHarnessPbar] = {}

    @contextmanager
    def run_test(
        self, desc: str | None = None, name: str = "DefaultName"
    ) -> Generator[TestHarnessPbar, Any, None]:
        """
        Runs a test with the given description and name.

        Args:
            desc (str | None): A description of the test. Defaults to None.
            name (str): The name of the test. Defaults to "DefaultName".

        Yields:
            Generator[TestHarnessPbar, Any, None]: A progress bar for the test.

        Raises:
            Any: Any exception raised during the test.

        """
        self.test_is_running.value = True
        pbar = TestHarnessPbar(desc=desc)
        self.pbars[name] = pbar
        try:
            yield pbar
        except Exception as e:
            pbar.__exit__(type(e), e, traceback.format_exc())
            self.end_test(name)
        finally:
            pbar.__exit__(None, None, None)
            self.end_test(name)

    def get_progress_percentage(self, name: str = "DefaultName") -> float:
        """
        Returns the progress percentage of a progress bar with the given name.
        If the progress bar does not exist,
          returns 0.0.
        If the progress bar's total is None,
          returns 0.0.
        If the progress bar's total is 0 and the test is running,
          returns 100.0.
        If the progress bar's total is 0 and the test is not running,
          returns 0.0.
        Otherwise, returns the progress percentage as a float.

        :param name: The name of the progress bar to get the
          progress percentage of.
        :type name: str
        :return: The progress percentage of the progress bar with the
          given name.
        :rtype: float
        """
        if name not in self.pbars:
            return 0.0
        pbar = self.pbars[name]
        if pbar.total is None:
            return 0.0
        if pbar.total == 0 and self.test_is_running:
            return 100.0
        elif pbar.total == 0:
            return 0.0
        return pbar.get_th_progress() / pbar.total * 100

    def end_test(self, name: str = "DefaultName") -> None:
        """
        Removes the progress bar associated with the given test name and sets
          the test_is_running flag to False.

        Args:
            name (str): The name of the test whose progress bar needs to be
              removed. Defaults to "DefaultName".
        """
        del self.pbars[name]
        self.test_is_running.value = False


if __name__ == "__main__":
    # run the app
    create_app().run()
