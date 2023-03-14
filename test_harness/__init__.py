"""
Creates the test harness app
"""
import os
from typing import Mapping, Optional, Callable, Union

from flask import Flask, request, make_response, Response
from werkzeug.datastructures import FileStorage
from test_harness.config.config import HarnessConfig


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
    """
    def __init__(
        self,
        import_name: str,
        harness_config_path: Optional[str] = None,
        static_url_path: Optional[str] = None,
        static_folder: Optional[Union[str, os.PathLike]] = "static",
        static_host: Optional[str] = None,
        host_matching: bool = False, subdomain_matching: bool = False,
        template_folder: Optional[Union[str, os.PathLike]] = "templates",
        instance_path: Optional[str] = None,
        instance_relative_config: bool = False,
        root_path: Optional[str] = None
    ) -> None:
        """Constructor method
        """
        self.harness_config = HarnessConfig(config_path=harness_config_path)
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
            root_path
        )

    def upload_uml_files(self) -> Response:
        """Function to handle the upload of UML files

        :return: 200 response if files uploaded successfully and
        400 if unsuccessful
        :rtype: :class:`Response`
        """
        # requests must be of type multipart/form-data
        if request.mimetype != "multipart/form-data":
            return make_response(
                "mime-type must be multipart/form-data\n",
                400
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
            uploaded_file_name == ''
            for uploaded_file_name in uploaded_files_names
        ):
            return make_response(
                "One of the uploaded files has no filename\n",
                400
            )

        # check if some of the files have the same name
        if len(set(uploaded_files_names)) < len(uploaded_files_names):
            return make_response(
                "At least two of the uploaded files share the same filename\n",
                400
            )

        for uploaded_file in uploaded_files:
            handle_uploaded_file(
                uploaded_file, self.harness_config.uml_file_store
            )

        return make_response("Files uploaded successfully\n", 200)


def create_app(
    harness_config_path: Optional[str] = None,
    test_config: Optional[Mapping] = None
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
        instance_relative_config=True
    )
    app.config.from_mapping()

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # route to upload uml
    wrap_function_app(
        app.upload_uml_files,
        "/uploadUML",
        ["POST"],
        app
    )

    return app


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


if __name__ == "__main__":
    # run the app
    create_app().run()
