from flask import Flask, request, jsonify
import jwt
import mysql.connector
import os
import bcrypt
from dotenv import load_dotenv
import requests
from functools import wraps
from itinerary import generate_itinerary

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

def jwt_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Extract token from Authorization header
            token = request.headers.get('Authorization').split()[1]
            
            # Decode and verify the JWT token
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            
            # Add the decoded token to the request context
            request.decoded_token = decoded_token
            
            return func(*args, **kwargs)
        except Exception as e:
            # Unauthorized access or invalid token
            response_data = {
                "status": 401,
                "message": "Unauthorized",
                "data": None
            }
            return jsonify(response_data), 401

    return wrapper

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
        db_cursor.execute("INSERT INTO users (name, email, phone_number, password, interests, created_at) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)", (name, email, phone_number, hashed_password, interests))        
        db_connection.commit()

        db_cursor.execute("SELECT created_at FROM users WHERE email = %s", (email,))
        created_at = db_cursor.fetchone()['created_at']

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
                    "phone": phone_number,
                    "created_at": created_at
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
    
@app.route('/account', methods=['GET'])
@jwt_required
def account():
    try:
        # Get the email from the decoded token in the request context
        email = request.decoded_token['email']

        # Query the database to get the user's account information based on the email
        db_cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = db_cursor.fetchone()
        print(user)

        if not user:
            # User not found
            response_data = {
                "status": 404,
                "message": "User not found",
                "data": None
            }
            return jsonify(response_data), 404

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "account": {
                    "name": user['name'],
                    "email": user['email'],
                    "phone": user['phone_number'],
                    "created_at": user['created_at']
                },
                "preferences": user['interests'].split(',') if user['interests'] else []
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

@app.route('/pois/categories', methods=['GET'])
def get_categories():
    try:
        # Query the database to get the categories
        db_cursor.execute("SELECT id, name, image FROM category")
        categories = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": categories
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


@app.route('/city/<int:city_id>/itinerary', methods=['GET'])
def get_itinerary(city_id):
    # Query the database to get the city name based on the city_id
    db_cursor.execute("SELECT kota FROM pois WHERE attraction_id = %s", (city_id,))
    result = db_cursor.fetchone()
    print("=============================================")
    print(result)

    if not result:
        # City not found
        response_data = {
            "status": 404,
            "message": "City not found",
            "data": None
        }
        return jsonify(response_data), 404

    city_name = result['kota']

    # Get the value of the 'days' query parameter
    num_days = int(request.args.get('days', 1))

    # Generate the itinerary data based on the city name and number of days
    itinerary_data = generate_itinerary(city_name, num_days)

    # Divide the itinerary data into an array of days
    itinerary_per_day = []
    for day in range(1, num_days + 1):
        poi_per_day = []
        for poi in itinerary_data:
            if poi['hari'] == day:
                poi_data = {
                    "id": poi['attraction_id'],
                    "name": poi['nama'],
                    "location": poi['kota'],
                    "image": poi['img'],
                    "tickets": {
                        "is_ticketing_enabled": True,
                        "adult_price": poi['adult_price'],
                        "child_price": poi['child_price']
                    }
                }
                poi_per_day.append(poi_data)
        day_data = {
            "day": day,
            "poi": poi_per_day
        }
        itinerary_per_day.append(day_data)

    # Return the response as JSON
    return jsonify({
        "status": 200,
        "message": "OK",
        "data": itinerary_per_day
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

# -------------------------------------------------------------------

# # Define a sample list of POI data
# import csv

# poi_data = []

# # Open the CSV file
# with open('data.csv', 'r') as file:
#     # Create a CSV reader object
#     csv_reader = csv.DictReader(file)
    
#     # Read each row of the CSV file
#     for row in csv_reader:
#         # Create a dictionary for each row
#         poi = {
#             "id": int(row["attraction_id"]),
#             "name": row["nama"],
#             "location": row["kota"],
#             "image": row["img"]
#         }
        
#         # Add the dictionary to the poi_data list
#         poi_data.append(poi)

# # Print the retrieved data
# for poi in poi_data:
#     print(poi)

# @app.route('/poi', methods=['GET'])
# def get_poi():
#     category = request.args.get('category')

#     # Filter the POI data based on the category
#     filtered_data = [poi for poi in poi_data if poi['category'] == category]

#     response = {
#         "status": 200,
#         "message": "OK",
#         "size": len(filtered_data),
#         "page": 1,
#         "data": filtered_data
#     }
#     return jsonify(response)

# if __name__ == '__main__':
#     app.run()

# # -------------------------------------------------------------------

# # Function to read POI data from the CSV file
# def read_poi_data():
#     poi_data = []
#     with open('poi_data.csv', 'r') as file:
#         csv_reader = csv.DictReader(file)
#         for row in csv_reader:
#             poi_data.append(row)
#     return poi_data

# # Function to get POI data by ID
# def get_poi_by_id(poi_id):
#     poi_data = read_poi_data()
#     for poi in poi_data:
#         if int(poi['id']) == poi_id:
#             return poi
#     return None

# # API endpoint to retrieve POI data by ID
# @app.route('/poi/<int:poi_id>', methods=['GET'])
# def get_poi(poi_id):
#     poi = get_poi_by_id(poi_id)
#     if poi is not None:
#         # Construct the response with POI data
#         response = {
#             "status": 200,
#             "message": "OK",
#             "data": {
#                 "id": int(poi["id"]),
#                 "name": poi["name"],
#                 "location": poi["location"],
#                 "image": poi["image"],
#                 "background_story": poi["deskripsi"],
#                 "position": {
#                     "long": float(poi["longtitude"]),
#                     "lat": float(poi["latitude"])
#                 },
#                 "guides": [
#                     {
#                         "id": int(poi["guide1_id"]),
#                         "name": poi["guide1_name"],
#                         "price": int(poi["guide1_price"]),
#                         "image": poi["guide1_image"],
#                         "time_duration_in_min": int(poi["guide1_duration"])
#                     },
#                     {
#                         "id": int(poi["guide2_id"]),
#                         "name": poi["guide2_name"],
#                         "price": int(poi["guide2_price"]),
#                         "image": poi["guide2_image"],
#                         "time_duration_in_min": int(poi["guide2_duration"])
#                     },
#                     {
#                         "id": int(poi["guide3_id"]),
#                         "name": poi["guide3_name"],
#                         "price": int(poi["guide3_price"]),
#                         "image": poi["guide3_image"],
#                         "time_duration_in_min": int(poi["guide3_duration"])
#                     }
#                 ],
#                 "tickets": {
#                     "is_ticketing_enabled": bool(poi["ticketing_enabled"]),
#                     "adult_price": int(poi["adult_price"]),
#                     "child_price": int(poi["child_price"])
#                 },
#                 "galleries": [
#                     {
#                         "id": int(poi["gallery1_id"]),
#                         "name": poi["gallery1_name"],
#                         "is_from_wisnu_team": bool(poi["gallery1_wisnu_team"]),
#                         "is_vr_capable": bool(poi["gallery1_vr_capable"]),
#                         "image": poi["gallery1_image"],
#                         "created_at": poi["gallery1_created_at"]
#                     },
#                     {
#                         "id": int(poi["gallery2_id"]),
#                         "name": poi["gallery2_name"],
#                         "is_from_wisnu_team": bool(poi["gallery2_wisnu_team"]),
#                         "is_vr_capable": bool(poi["gallery2_vr_capable"]),
#                         "image": poi["gallery2_image"],
#                         "created_at": poi["gallery2_created_at"]
#                     },
#                     {
#                         "id": int(poi["gallery3_id"]),
#                         "name": poi["gallery3_name"],
#                         "is_from_wisnu_team": bool(poi["gallery3_wisnu_team"]),
#                         "is_vr_capable": bool(poi["gallery3_vr_capable"]),
#                         "image": poi["gallery3_image"],
#                         "created_at": poi["gallery3_created_at"]
#                     }
#                 ]
#             }
#         }
#         return jsonify(response)
#     else:
#         response = {
#             "status": 404,
#             "message": "POI not found"
#         }
#         return jsonify(response), 404

# if __name__ == '__main__':
#     app.run()

# # -------------------------------------------------------------------

# # Function to read cities data from CSV
# def read_cities_from_csv():
#     cities = []
#     with open('cities.csv', 'r') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             cities.append(row)
#     return cities

# # Get cities endpoint
# @app.route('/cities', methods=['GET'])
# def get_cities():
#     # Read cities data from CSV
#     cities = read_cities_from_csv()

#     # Check if preview parameter is set to true
#     preview = request.args.get('preview')
#     if preview and preview.lower() == 'true':
#         # Return limited size (preview) response
#         size = 5  # Set the preview size here
#         page = 1   # Set the preview page here
#         data = cities[:size]
#         response = {
#             "status": 200,
#             "message": "OK",
#             "preview": True,
#             "size": size,
#             "page": page,
#             "data": data
#         }
#     else:
#         # Return full size (paginated) response
#         size = int(request.args.get('size', len(cities)))
#         page = int(request.args.get('page', 1))
#         start_index = (page - 1) * size
#         end_index = start_index + size
#         data = cities[start_index:end_index]
#         response = {
#             "status": 200,
#             "message": "OK",
#             "preview": False,
#             "size": size,
#             "page": page,
#             "data": data
#         }
    
#     return jsonify(response)

# if __name__ == '__main__':
#     app.run()

# # -------------------------------------------------------------------

# # Function to read cities data from CSV
# def read_cities_from_csv():
#     cities = []
#     with open('cities.csv', 'r') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             cities.append(row)
#     return cities

# # Function to read POIs data from CSV
# def read_pois_from_csv():
#     pois = []
#     with open('pois.csv', 'r') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             pois.append(row)
#     return pois

# # Get city detail endpoint
# @app.route('/city/<int:city_id>', methods=['GET'])
# def get_city_detail(city_id):
#     # Read cities and POIs data from CSV
#     cities = read_cities_from_csv()
#     pois = read_pois_from_csv()

#     # Find the city with the given city_id
#     city = next((c for c in cities if int(c['id']) == city_id), None)
#     if city:
#         # Filter POIs for the specific city_id
#         city_pois = [poi for poi in pois if int(poi['city_id']) == city_id]

#         # Prepare the response
#         response = {
#             "status": 200,
#             "message": "OK",
#             "data": {
#                 "id": int(city['id']),
#                 "name": city['name'],
#                 "location": city['location'],
#                 "description": city['description'],
#                 "image": city['image'],
#                 "poi": city_pois
#             }
#         }
#     else:
#         # City not found
#         response = {
#             "status": 404,
#             "message": "City not found"
#         }
    
#     return jsonify(response)

# if __name__ == '__main__':
#     app.run()

#     # -------------------------------------------------------------------

# # Function to read city itineraries from CSV
# def read_city_itineraries_from_csv(city_id, num_days):
#     itineraries = []
#     with open('city_itineraries.csv', 'r') as file:
#         reader = csv.DictReader(file)
#         for row in reader:
#             if int(row['city_id']) == city_id and int(row['day']) <= num_days:
#                 itineraries.append(row)
#     return itineraries

# # Get city itineraries endpoint
# @app.route('/city/<int:city_id>/itinerary', methods=['GET'])
# def get_city_itineraries(city_id):
#     # Get query parameter 'days' from the request
#     num_days = int(request.args.get('days', default=1))

#     # Read city itineraries from CSV
#     city_itineraries = read_city_itineraries_from_csv(city_id, num_days)

#     # Prepare the response
#     response = {
#         "status": 200,
#         "message": "OK",
#         "data": []
#     }

#     # Group itineraries by day
#     grouped_itineraries = {}
#     for itinerary in city_itineraries:
#         day = int(itinerary['day'])
#         if day not in grouped_itineraries:
#             grouped_itineraries[day] = []
#         grouped_itineraries[day].append(itinerary)

#     # Create the response data structure
#     for day, itineraries in grouped_itineraries.items():
#         day_data = {
#             "day": day,
#             "poi": []
#         }
#         for itinerary in itineraries:
#             poi = {
#                 "id": int(itinerary['poi_id']),
#                 "name": itinerary['poi_name'],
#                 "location": itinerary['poi_location'],
#                 "image": itinerary['poi_image'],
#                 "tickets": {
#                     "is_ticketing_enabled": bool(itinerary['is_ticketing_enabled']),
#                     "adult_price": int(itinerary['adult_price']),
#                     "child_price": int(itinerary['child_price'])
#                 }
#             }
#             day_data['poi'].append(poi)
#         response['data'].append(day_data)

#     return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

