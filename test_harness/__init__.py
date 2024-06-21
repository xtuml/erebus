# pylint: disable=R0913
"""
Creates the test harness app
"""
import os
import glob
import shutil
import traceback
from uuid import uuid4
from zipfile import ZipFile
from ctypes import c_int, c_bool
from multiprocessing import Value
from contextlib import contextmanager
from typing import Mapping, Optional, Callable, Union, Any, Generator
from flask_cors import CORS

from tempfile import TemporaryDirectory
from configparser import ConfigParser

from flask import Flask, request, make_response, Response, jsonify, send_file

from flasgger import Swagger
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest
from tqdm import tqdm
import yaml

from test_harness.config.config import TestConfig, HarnessConfig
from test_harness.utils import AsyncTestStopper

try:
    from test_harness.protocol_verifier.config.config import (
        ProtocolVerifierConfig,
    )
except Exception as error:
    print(f"Error loading in ProtocolVerifierConfig: {error}")
from test_harness.utils import create_zip_file_from_folder


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
        config_parser: ConfigParser,
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
        try:
            if config_parser["protocol-verifier"]:
                self.harness_config = ProtocolVerifierConfig(
                    config_parser=config_parser
                )
        except KeyError:
            self.harness_config = HarnessConfig(config_parser=config_parser)
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
        self.test_stopper = AsyncTestStopper()

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
        # If using swagger api, get the array of files
        files = request.files.getlist("file")
        if files:
            uploaded_files = files
        else:
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
        test_name = (
            request_json["TestName"] if "TestName" in request_json else None
        )
        test_name, test_output_directory = create_test_output_directory(
            base_output_path=self.harness_config.report_file_store,
            test_name=test_name,
        )
        test_to_run["TestOutputDirectory"] = test_output_directory
        response_json["TestOutputFolder"] = (
            f"Tests under name {test_name} in the directory"
            f"{test_output_directory}"
        )
        test_config = TestConfig()
        if os.path.exists(
            os.path.join(test_output_directory, "test_config.yaml")
        ):
            test_config.parse_from_yaml(
                os.path.join(test_output_directory, "test_config.yaml")
            )
        if "TestConfig" in request_json:
            test_config.parse_from_dict(request_json["TestConfig"])
        test_to_run["TestConfig"] = test_config
        response_json["TestConfig"] = test_config.config_to_dict()
        with open(
            os.path.join(test_output_directory, "used_config.yaml"), "w"
        ) as file:
            yaml.dump(response_json["TestConfig"], file)
        self.test_to_run = test_to_run
        return (True, response_json)

    def upload_named_zip_files(self) -> Response:
        """Handler for uploading a named zip file for a test

        :return: Returns a :class:`Response`
        :rtype: :class:`Response`
        """
        # requests must be of type multipart/form-data
        if request.mimetype != "multipart/form-data":
            return make_response(
                "mime-type must be multipart/form-data\n", 400
            )
        # handle zip files; swagger can't combine testName and file
        # into 1 argument like the curl command does so swagger passes
        # both TestName and file as separate entities. We check here if
        # TestName exits and if so set it to upload_file_identifier for
        # swagger api call to work correctly
        try:
            for uploaded_file_identifier, file in request.files.items():
                if "TestName" in request.form:
                    uploaded_file_identifier = request.form["TestName"]
                handle_uploaded_zip_file(
                    file_storage=file,
                    name=uploaded_file_identifier,
                    save_file_dir_path=self.harness_config.report_file_store,
                )
        except Exception as error:
            return (
                f"Error uploading zip"
                f"file {uploaded_file_identifier}: {error}\n",
                400,
            )
        return "Zip archives uploaded successfully\n", 200

    def stop_test(self) -> Response:
        """API for stopping a test given a json POST request

        :return: Returns a :class:`Response`
        :rtype: :class:`Response`
        """
        try:
            json_dict = request.get_json()
            return self._handle_stop_test_json_request(json_dict)
        except BadRequest as error:
            return error.get_response()

    def _handle_stop_test_json_request(self, request_json: dict) -> Response:
        """Handler for stopping a test given a json POST request

        :param request_json: The request json sent as a python dictionary
        :type request_json: `dict`
        :return: Returns the response
        :rtype: `Response`
        """
        self.test_stopper.set()
        return ("Request to stop test successful\n", 200)

    def get_test_output_folder(self) -> Response:
        """Method to get the test output folder

        :return: Returns a reponse containing the test output folder data
        :rtype: `Reponse`
        """
        try:
            json_dict = request.get_json()
            return self._handle_get_test_output_folder_json_request(json_dict)
        except BadRequest as error:
            return error.get_response()

    def _handle_get_test_output_folder_json_request(
        self, request_json: dict
    ) -> Response:
        """Handler for getting the test output folder and returning it as a zip

        :param request_json: The request json sent as a python dictionary
        :type request_json: `dict`
        :return: Returns the response
        :rtype: `Response`
        """
        if "TestName" not in request_json:
            return ("Field 'TestName' not in request json\n", 400)
        test_name = request_json["TestName"]
        test_output_directory_path = os.path.join(
            self.harness_config.report_file_store, test_name
        )
        if not os.path.exists(test_output_directory_path):
            return (f"Test with name {test_name} does not exist\n", 400)
        with TemporaryDirectory() as temp_dir:
            zip_file_path = os.path.join(temp_dir, f"{test_name}.zip")
            create_zip_file_from_folder(
                test_output_directory_path, zip_file_path
            )
            return send_file(
                zip_file_path,
                mimetype="application/zip",
                as_attachment=True,
                download_name=f"{test_name}.zip",
            )

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
        return {"TestName", "TestConfig"}


def create_app(
    config_parser: ConfigParser,
    test_config: Optional[Mapping] = None,
) -> HarnessApp:
    """Creates HarnessApp(Flask)

    :param config_parser: :class: `ConfigParser`
    :type config_parser: Optional[str], optional
    :param test_config: Configuration test config, defaults to None
    :type test_config: :class:`Mapping`, optional
    :return: Returns a HarnessApp instance
    :rtype: :class:`HarnessApp`
    """
    # create and configure the app
    app = HarnessApp(
        __name__,
        config_parser=config_parser,
        instance_relative_config=True,
    )
    CORS(app)
    app.config.from_mapping()
    app.config["SWAGGER"] = {
        "openapi": "3.0.2",
        "title": "Test Harness",
        "description": "Package that runs a test harness for arbitrary "
        "system functional and performance testing. Provides base "
        "functionality to set up tests and send test files.",
        "version": "v0.01-beta",
        "termsOfService": None,
        "servers": [{"url": "http://127.0.0.1:8800"}],
        "components": {
            "schemas": {
                "StartTest": {
                    "type": "object",
                    "required": ["TestName"],
                    "properties": {
                        "TestName": {
                            "type": "string",
                            "example": "Name of Test Here",
                        },
                        "TestConfig": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "example": "Performance",
                                },
                                "performance_options": {
                                    "type": "object",
                                    "properties": {
                                        "num_files_per_sec": {
                                            "type": "number",
                                            "example": 10,
                                        },
                                    },
                                },
                                "num_workers": {
                                    "type": "number",
                                    "example": 0,
                                },
                                "aggregate_during": {
                                    "type": "boolean",
                                    "example": False,
                                },
                                "sample_rate": {
                                    "type": "number",
                                    "example": 0,
                                },
                                "low_memory": {
                                    "type": "boolean",
                                    "example": False,
                                },
                            },
                        },
                    },
                },
                "StartTestResponse": {
                    "type": "object",
                    "properties": {
                        "TestConfig": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "example": "Performance",
                                },
                                "performance_options": {
                                    "type": "object",
                                    "properties": {
                                        "job_event_gap": {
                                            "type": "number",
                                            "example": 1,
                                        },
                                        "num_files_per_sec": {
                                            "type": "number",
                                            "example": 10,
                                        },
                                        "round_robin": {
                                            "type": "boolean",
                                            "example": False,
                                        },
                                        "save_logs": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "shard": {
                                            "type": "boolean",
                                            "example": False,
                                        },
                                        "total_jobs": {
                                            "type": "number",
                                            "example": 10000,
                                        },
                                    },
                                },
                                "num_workers": {
                                    "type": "number",
                                    "example": 0,
                                },
                                "aggregate_during": {
                                    "type": "boolean",
                                    "example": False,
                                },
                                "sample_rate": {
                                    "type": "number",
                                    "example": 0,
                                },
                                "low_memory": {
                                    "type": "boolean",
                                    "example": False,
                                },
                                "event_gen_options": {
                                    "type": "object",
                                    "properties": {
                                        "invalid": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "max_sol_time": {
                                            "type": "number",
                                            "example": 120,
                                        },
                                        "solutions_limit": {
                                            "type": "number",
                                            "example": 100,
                                        },
                                    },
                                },
                                "max_different_sequences": {
                                    "type": "number",
                                    "example": 200,
                                },
                            },
                        },
                        "TestOutputFolder": {
                            "type": "string",
                            "example": "Tests under name <TestName> in the"
                            "directory /<path>/erebus/test_harness/"
                            "report_ouput/<TestName>",
                        },
                    },
                },
                "StopTest": {
                    "type": "object",
                    "description": "Currently an empty object",
                },
                "OutputData": {
                    "type": "object",
                    "required": ["TestName"],
                    "properties": {
                        "TestName": {
                            "type": "string",
                            "example": "Name of Test here",
                        }
                    },
                },
                "TestRunning": {
                    "type": "object",
                    "properties": {
                        "details": {
                            "type": "object",
                            "properties": {
                                "percent_done": {
                                    "type": "string",
                                    "example": "50%",
                                },
                                "running": {
                                    "type": "boolean",
                                    "example": True,
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    Swagger(app)

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
        """Endpoint to handle the upload of a profile file
        A profile for a performance test can be uploaded in the form
        of a CSV file. The profile provides specific points (given in seconds)
        in simulation time where the number of test files sent per second is
        described. The csv must have the following headers in the following
        order: "Time", "Number". The Test Harness will linearly interpolate
        between these times to a discretisation of 1 second and will calculate
        how many test files are sent within that second
        ---
        tags:
            - Upload
            - Optional
        requestBody:
            content:
                multipart/form-data:
                    schema:
                        type: object
                        required: ["file"]
                        description: file to upload
                        properties:
                            file:
                                type: string
                                format: binary
        responses:
            200:
                description: Files uploaded successfully
                content:
                    application/json:
                        schema:
                            type: string
                            example: Files uploaded successfully
            400:
                description: Files failed to upload - mime-type must be\
                multipart/form-data
        """
        return app.upload_profile()

    # route to upload test-files
    @app.route("/upload/test-files", methods=["POST"])
    def upload_test_files() -> None:
        """Test job files can be uploaded that suit the specific system
        being tested. This endpoint allows the upload of multiple test
        files and is of mime type multipart/form.
        ---
        tags:
            - Upload
            - Optional
        requestBody:
            content:
                multipart/form-data:
                    schema:
                        type: object
                        required: ["file"]
                        properties:
                            file:
                                type: array
                                items:
                                    type: string
                                    format: binary
        responses:
            200:
                description: Files uploaded successfully
                content:
                    application/json:
                        schema:
                            type: string
                            example: Files uploaded successfully
            415:
                description: Files failed to upload - mime-type must be\
                multipart/form-data
        """
        return app.upload_test_files()

    # route to start test
    @app.route("/startTest", methods=["POST"])
    def start_test() -> None:
        """Endpoint to handle starting an uploaded test
        ---
        tags:
            - Test
            - Start test
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/StartTest'
            description: Name and optional config of test to run
        responses:
            200:
                description: Test started successfully
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/StartTestResponse'

            400:
                description: Bad Request
            415:
                description: Unsupported Media Type.\
                Must include 'Content-Type application/json'
        """
        return app.start_test()

    @app.route("/isTestRunning", methods=["GET"])
    def test_is_running() -> None:
        """Endpoint to fetch currently running test progress
        ---
        tags:
            - Test
        parameters:
            - name: TestName
              in: query
              type: string
              required: true
              description: Name of test to view progress
        responses:
            200:
                description: returns % done only if running is true
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/TestRunning'

        """
        return app.test_is_running()

    # route to upload zip-files
    @app.route("/upload/named-zip-files", methods=["POST"])
    def upload_named_zip_files() -> None:
        """Endpoint to handle the starting of a specified test
        This is the recommended way of uploading Test Case zip files
        to the Test Harness. These can include all the test data required to
        run the specific test.
        ---
        tags:
            - Upload
            - Test
        requestBody:
            required: true
            content:
                multipart/form-data:
                    schema:
                        type: object
                        required: ["file", "TestName"]
                        properties:
                            file:
                                type: string
                                format: binary
                            TestName:
                                type: string
        responses:
            200:
                description: Files uploaded successfully
                content:
                    application/json:
                        schema:
                            type: string
                            example: Zip archives uploaded successfully
            400:
                description: Files failed to upload - mime-type must be\
                multipart/form-data OR File is not a zip file
        """
        return app.upload_named_zip_files()

    # route to stop test
    @app.route("/stopTest", methods=["POST"])
    def stop_test() -> None:
        """Endpoint to handle gracefully stopping a specified test
        To stop a test gracefully once it is running. Currently the JSON
        body accepted is empty.
        ---
        tags:
            - Test
            - Stop test
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/StopTest'
            description: Currently accepts empty JSON body
        responses:
            200:
                description: Request to stop test successful
                content:
                    application/json:
                        schema:
                            type: string
                            example: Request to stop test successful
            400:
                description: Failed to stop test
        """
        return app.stop_test()

    # route to retrieve test output folder
    @app.route("/getTestOutputFolder", methods=["POST"])
    def get_test_output_folder() -> None:
        """Endpoint to retrieve output data from a finished test.
        The JSON body should specify the TestName given in the /startTest
        endpoint requests used to start the test.
        ---
        tags:
            - Test
            - Get Output Data
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/OutputData'
            description: Name of Test to retrieve output data from
        responses:
            200:
                description: Output data fetched successfully
                content:
                    application/json:
                        schema:
                            type: string
                            format: binary
                            example: FileName.zip
            400:
                description: Test does not exist
        """
        return app.get_test_output_folder()

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
        return (
            "More than two files uploaded. A single file is required\n",
            400,
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
    return ("Files uploaded successfully\n", 200)


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


def handle_uploaded_zip_file(
    file_storage: FileStorage, name: str, save_file_dir_path: str
) -> None:
    """Helper function to create output path and save uploaded file

    :param file_storage: FileStroage class containing the uploaded file
    and metadata
    :type file_storage: class:`FileStorage`
    :param name: Name of the test
    :type name: `str`
    :param save_file_dir_path: Path of folder to save the file in
    :type save_file_dir_path: str
    """
    _, test_output_directory_path = create_test_output_directory(
        base_output_path=save_file_dir_path, test_name=name
    )
    # clean test output directory before unzipping files into it
    for file in os.listdir(test_output_directory_path):
        file_path = os.path.join(test_output_directory_path, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            pass
    # unzip the file to the test output directory
    with ZipFile(file_storage.stream) as zip_file:
        # find the common path which must be the highest level directory
        common_path = os.path.commonpath(
            (member.filename for member in zip_file.infolist())
        )
        zip_file.extractall(test_output_directory_path)
        if common_path == "":
            return
        extracted_path = os.path.join(test_output_directory_path, common_path)
        # move contents from extracted path into the correct folder and remove
        # extracted folder
        for path in glob.glob(
            "*",
            root_dir=extracted_path,
        ):
            shutil.move(
                os.path.join(extracted_path, path),
                os.path.join(test_output_directory_path, path),
            )
        shutil.rmtree(extracted_path)


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
    base_output_path: str, test_name: str | None = None
) -> tuple[str, str]:
    """Method to create a test output directory given base output path and a
    test name. If no test name is given a uuid is given to the test and
    returned along with the directory path

    :param base_output_path: The base path to output the test directory to
    :type base_output_path: `str`
    :param test_name: The identifier for the test, defaults to `None`
    :type test_name: `str` | `None`, optional
    :return: Returns a tuple of:
    * the test name
    * the path to the directory for the test
    :rtype: `tuple`[`str`, `str`]
    """
    if not test_name:
        test_name = str(uuid4())
    test_output_directory_path = os.path.join(base_output_path, test_name)
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
        self.th_progress.value += n
        self.n = self.th_progress.value
        super().update(0)

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
