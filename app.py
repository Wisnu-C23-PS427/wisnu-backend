from flask import Flask, request, jsonify
import jwt
import mysql.connector
import os
import bcrypt
from dotenv import load_dotenv

load_dotenv('.env')

app = Flask(__name__)

# Secret key for JWT
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Connect to the MySQL database
db_connection = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

# Create a cursor to interact with the database
db_cursor = db_connection.cursor(dictionary=True)

@app.route('/register', methods=['POST'])
def register():
    try:
        # Get the request data
        data = request.json

        # Extract registration data from the request
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Check if user already exists
        db_cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = db_cursor.fetchone()

        if existing_user:
            # User already exists
            response_data = {
                "status": 400,
                "message": "User already exists",
                "data": None
            }
            return jsonify(response_data), 400

        # Insert the user into the database
        db_cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
        db_connection.commit()

        # Generate JWT token
        user_id = db_cursor.lastrowid
        token = jwt.encode({'user_id': user_id}, app.config['SECRET_KEY'], algorithm='HS256')

        # Create the response data with the token
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "token": token
            }
        }

        # Return the response as JSON
        return jsonify(response_data), 200

    except Exception as e:
        # Server error
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        # Get the request data
        data = request.json

        # Extract email and password from the request
        email = data.get('email')
        password = data.get('password')

        # Query the database to find the user
        db_cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = db_cursor.fetchone()

        if user is None or not bcrypt.checkpw_hash(password.encode('utf-8'), user['password']):
            # Unauthorized access (invalid email or password)
            response_data = {
                "status": 401,
                "message": "Wrong email or password",
                "data": None
            }
            return jsonify(response_data), 401

        # Generate JWT token
        token = jwt.encode({'user_id': user['id']}, app.config['SECRET_KEY'], algorithm='HS256')

        # Create the response data with the token
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "token": token
            }
        }

        # Return the response as JSON
        return jsonify(response_data), 200

    except Exception as e:
        # Server error
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500

@app.errorhandler(400)
def handle_client_error(e):
    # Client error
    response_data = {
        "status": 400,
        "message": f"Reason: {str(e)}",
        "data": None
    }
    return jsonify(response_data), 400

if __name__ == '__main__':
    app.run()
