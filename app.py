from flask import Flask, request, jsonify
import jwt
import mysql.connector
import os
import bcrypt
from dotenv import load_dotenv
import requests
from ml import generate_itinerary

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

# Store active tokens (for authenticated users)
active_tokens = set()

@app.route('/auth/register', methods=['POST'])
def register():
    try:
        # Get the request data
        data = request.json

        # Extract registration data from the request
        name = data.get('name')
        email = data.get('email')
        phone_number = data.get('phone_number')
        password = data.get('password')
        interests = data.get('interests')
        interests = ','.join(interests)

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
        db_cursor.execute("INSERT INTO users (name, email, phone_number, password, interests) VALUES (%s, %s, %s, %s, %s)", (name, email, phone_number, hashed_password, interests))
        db_connection.commit()

        # Generate JWT token
        token = jwt.encode({'email': email}, app.config['SECRET_KEY'], algorithm='HS256')

        # Add the token to the active_tokens set
        active_tokens.add(token)
        print(f"User {email} registered")

        # Create the response data
        response_data = {
            "status": 200,
            "message": "Verify mail",
            "data": {
                "account": {
                    "name": name,
                    "email": email,
                    "phone": phone_number
                },
                "preference": interests.split(','),
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


@app.route('/auth/login', methods=['POST'])
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

        if user is None or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # Unauthorized access (invalid email or password)
            response_data = {
                "status": 401,
                "message": "Wrong email or password",
                "data": None
            }
            return jsonify(response_data), 401

        # Generate JWT token
        token = jwt.encode({'email': email}, app.config['SECRET_KEY'], algorithm='HS256')

        # Add the token to the active_tokens set
        active_tokens.add(token)
        print(f"User {email} logged in")

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

@app.route('/auth/logout', methods=['POST'])
def logout():
    try:
        # Get the request data
        data = request.json

        # Extract the token from the request
        token = data.get('token')

        # Remove the token from the active_tokens set
        active_tokens.remove(token)
        print(f"User logged out")

        # Create the response data
        response_data = {
            "status": 200,
            "message": "Logged out successfully",
            "data": None
        }

        # Return the response as JSON
        return jsonify(response_data), 200

    except KeyError:
        # Token not found in the active_tokens set
        response_data = {
            "status": 401,
            "message": "Invalid token",
            "data": None
        }
        return jsonify(response_data), 401
    
@app.route('/itinerary', methods=['POST'])
def itinerary():
    GPT_KEY = os.getenv('GPT_KEY')
    HEADERS = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GPT_KEY}'
    }

    data = request.get_json()
    days = data.get('days')
    city = data.get('city')
    start_date = data.get('startDate')

    parts = city.split(' ')
    if len(parts) > 5:
        return jsonify({'message': 'please reduce size of request'}), 400

    if days > 10:
        days = 10

    base_prompt = f"what is an ideal and complete itinerary for {days} days and starting out on {start_date} in {city}?"

    try:
        response = requests.post('https://api.openai.com/v1/completions', headers=HEADERS, json={
            'model': 'text-davinci-003',
            'prompt': base_prompt,
            'temperature': 0,
            'max_tokens': 550
        })
        response_data = response.json()
        itinerary = response_data['choices'][0]['text']
        
        points_of_interest_prompt = 'Extract the points of interest out of this text, with no additional words, separated only by commas, dont use spaces nor newlines, but use space between words in names of the places (example= "Eiffel Tower,Mount Everest,Great Bridge of China): ' + itinerary
        response = requests.post('https://api.openai.com/v1/completions', headers=HEADERS, json={
            'model': 'text-davinci-003',
            'prompt': points_of_interest_prompt,
            'temperature': 0,
            'max_tokens': 550
        })
        response_data = response.json()
        points_of_interests = response_data['choices'][0]['text']

        return jsonify({
            'message': 'success',
            'itinerary': itinerary,
            'points_of_interests': points_of_interests
        })

    except Exception as e:
        # Server error
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500


@app.route('/city/<string:city_name>/itinerary', methods=['GET'])
def get_itinerary(city_name):
    # Get the value of the 'days' query parameter
    num_days = int(request.args.get('days', 1))

    # Generate the itinerary data based on the city name and number of days
    itinerary_data = generate_itinerary(city_name, num_days)

    # Return the response as JSON
    return jsonify({
        "status": 200,
        "message": "OK",
        "data": itinerary_data
    })

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
    app.run(host='0.0.0.0', port=80)

# -------------------------------------------------------------------

# Define a sample list of POI data
import csv

poi_data = []

# Open the CSV file
with open('data.csv', 'r') as file:
    # Create a CSV reader object
    csv_reader = csv.DictReader(file)
    
    # Read each row of the CSV file
    for row in csv_reader:
        # Create a dictionary for each row
        poi = {
            "id": int(row["attraction_id"]),
            "name": row["nama"],
            "location": row["kota"],
            "image": row["img"]
        }
        
        # Add the dictionary to the poi_data list
        poi_data.append(poi)

# Print the retrieved data
for poi in poi_data:
    print(poi)

@app.route('/poi', methods=['GET'])
def get_poi():
    category = request.args.get('category')

    # Filter the POI data based on the category
    filtered_data = [poi for poi in poi_data if poi['category'] == category]

    response = {
        "status": 200,
        "message": "OK",
        "size": len(filtered_data),
        "page": 1,
        "data": filtered_data
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run()