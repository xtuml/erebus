"""
Creates the test harness app
"""
import os
from typing import Mapping, Optional, Callable

from flask import Flask, request, make_response, Response
from werkzeug.datastructures import FileStorage


def create_app(test_config: Optional[Mapping] = None) -> Flask:
    """Create flask app

    :param test_config: Configuration test config, defaults to None
    :type test_config: :class:`Mapping`, optional
    :return: Returns a Flask instance
    :rtype: :class:`Flask`
    """
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
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
        upload_uml_files,
        "/uploadUML",
        ["POST"],
        app
    )

    return app


def upload_uml_files() -> Response:
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

    for uploaded_file_identifier in request.files:
        uploaded_file: FileStorage = request.files[uploaded_file_identifier]
        if uploaded_file.filename != '':
            # TODO: Replace with file handling function
            print(uploaded_file.filename)
        else:
            return make_response(
                "One of the uploaded files has no filename\n",
                400
            )
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


if __name__ == "__main__":
    # run the app
    create_app().run()
