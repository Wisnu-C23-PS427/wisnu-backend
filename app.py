from flask import Flask, request, jsonify
import jwt

app = Flask(__name__)

# Dummy user data for demonstration
users = [
    {"id": 1, "email": "user1@mail.com", "password": "password1"},
    {"id": 2, "email": "user2@mail.com", "password": "password2"},
    {"id": 3, "email": "user3@mail.com", "password": "password3"}
]

# Secret key for JWT
app.config['SECRET_KEY'] = 'secretkey'

@app.route('/login', methods=['POST'])
def login():
    try:
        # Get the request data
        data = request.json

        # Extract email and password from the request
        email = data.get('email')
        password = data.get('password')

        # Find the user in the dummy user data
        user = next((user for user in users if user['email'] == email), None)

        if user is None or user['password'] != password:
            # Unauthorized access (invalid email or password)
            response_data = {
                "status": 401,
                "message": "Unauthorized",
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
