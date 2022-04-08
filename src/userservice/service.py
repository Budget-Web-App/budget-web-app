from shared import __generate_new_token, __validate_new_user, get_private_key, get_public_key, get_token_data, verify_token
from __init__ import users_db, months_db, app
from decorators import exception_handler, requires_token, required_args, ArgumentError, SQLLookupError, EndpointPermissionError, CategoryLookupError
from core import logger

from flask import request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import bcrypt

import bleach
from werkzeug.utils import secure_filename
from zipfile import ZipFile


def create_app():
    """Flask application factory to create instances
    of the Userservice Flask App
    """

    @app.route("/signin", methods=["Get"])
    @exception_handler
    def signin():
        logger.debug('Sanitizing login input.')
        raw_email = request.args.get('email')

        if raw_email is None:
            raise ArgumentError("No email argument provided", 419)

        raw_password = request.args.get('password')

        if raw_password is None:
            raise ArgumentError("No password argument provided", 419)

        remember_me = request.form.get('rememberme', False, bool)

        email = bleach.clean(raw_email)
        password = bleach.clean(raw_password)

        user = users_db.get_user(email)
        if user is None:
            raise SQLLookupError('user {0} does not exist'.format(email), 404)

        # Validate the password
        if not bcrypt.checkpw(password.encode('utf-8'), user["passhash"]):
            raise EndpointPermissionError('Invalid login', 401)

        # Generates token
        token = __generate_new_token(user)

        return jsonify({'token': token.decode("utf-8")}), 200

    @app.route("/signup", methods=["POST"])
    @exception_handler
    def signup():
        try:
            logger.debug('Sanitizing input.')
            req = {k: bleach.clean(v) for k, v in request.form.items()}
            __validate_new_user(req)

            if users_db.get_user(req["email"]) is not None:
                raise LookupError(
                    "email {0} is already in use".format(req["email"]))

            accountid = users_db.generate_userid()

            logger.debug('generating password hash')
            password = req["password"]
            salt = bcrypt.gensalt()
            passhash = bcrypt.hashpw(password.encode('utf-8'), salt)
            logger.info('Successfully generated password hash')

            user_data = {
                "userid": accountid,
                "email": req["email"],
                "timezone": req["timezone"],
                "passhash": passhash
            }

            # Add user_data to database
            logger.debug("Adding user to the database")
            users_db.add_user(user_data)
            logger.info("Successfully created user.")

            user = users_db.get_user(user_data["email"])
            del user["passhash"]

            return jsonify(user), 201
        except UserWarning as warn:
            logger.error("Error creating new user: %s", str(warn))
            return str(warn), 400
        except NameError as err:
            logger.error("Error creating new user: %s", str(err))
            return str(err), 409
        except SQLAlchemyError as err:
            logger.error("Error creating new user: %s", str(err))
            return 'failed to create user', 500
        except Exception as e:
            return str(e), 404

    @app.route('/<user_id>/budgets/<budget_id>/months', methods=['GET'])
    @exception_handler
    @requires_token
    def get_budget_months(user_id: str, budget_id: str):
        months = months_db.get_months(budget_id)

        return jsonify({"values": months}), 201

    return app


if __name__ == "__main__":
    # Create an instance of flask server when called directly
    USERSERVICE = create_app()
    USERSERVICE.run(debug=True, use_reloader=True)
