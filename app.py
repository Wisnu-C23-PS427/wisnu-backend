from flask import Flask, request, jsonify
import jwt
import mysql.connector
import os
import bcrypt
from dotenv import load_dotenv
from functools import wraps
from ml.itinerary.itinerary import generate_itinerary

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
    
@app.route('/events/<int:id>', methods=['GET'])
def get_event(id):
    db_cursor.execute("SELECT * FROM events WHERE attraction_id = %s", (id,))
    event = db_cursor.fetchone()

    if event is None:
        return jsonify({'message': 'Event not found'}), 404

    event_data = {
        'attraction_id': event['attraction_id'],
        'nama': event['nama'],
        'description': event['description'],
        'location': event['kota'],
        'img': event['img'],
        'date': event['date']
    }

    response_data = {
        "status": 200,
        "message": "OK",
        "data": event_data
    }

    return jsonify(response_data), 200

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

@app.route('/pois', methods=['GET'])
def get_pois():
    try:
        # Get the preview flag, size, and page from the query parameters
        preview = request.args.get('preview')
        size = request.args.get('size')
        page = request.args.get('page')

        # Set the default values if parameters are not provided
        if preview is None or preview.lower() == 'true':
            preview = True
        else:
            preview = False

        if size is not None:
            size = int(size)

        if page is not None:
            page = int(page)

        # Determine the limit and offset based on the preview flag and pagination parameters
        if preview:
            limit = 5  # Set the limit to a predefined value for preview mode
            offset = 0
        elif size is not None and page is not None:
            limit = size
            offset = (page - 1) * size
        else:
            limit = None  # No limit if size and page are not provided
            offset = None

        # Build the SQL query based on the limit and offset
        sql_query = "SELECT attraction_id AS id, nama AS name, kota AS location, img AS image FROM pois"

        # Add ORDER BY clause to sort by total_rating in descending order
        sql_query += " ORDER BY total_rating ASC"

        query_params = ()
        if limit is not None:
            sql_query += " LIMIT %s"
            query_params += (limit,)
        if offset is not None:
            sql_query += " OFFSET %s"
            query_params += (offset,)

        # Execute the SQL query
        db_cursor.execute(sql_query, query_params)
        pois = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "preview": preview,
            "size": size,
            "page": page,
            "data": pois
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

# ------POI DETAILS (error 505)--------

@app.route('/poi/<int:poi_id>', methods=['GET'])
def get_poi_details(poi_id):
    db_cursor.execute("SELECT * FROM poi WHERE attraction_id = %s", (poi_id,))
    poi = db_cursor.fetchone()

    if poi is None:
        return jsonify({'message': 'POI not found'}), 404

    poi_data = {
        'id': poi['attraction_id'],
        'name': poi['nama'],
        'location': poi['kota'],
        'image': poi['img'],
        'background_story': poi['description'],
        'position': {
            'long': poi['longitude'],
            'lat': poi['latitude']
        },
        'guides': [
            {
                'id': 1,
                'name': 'Guide Name',
                'price': 10000,
                'image': 'www.path/to/guide_image.jpg',
                'time_duration_in_min': 60
            },
            {
                'id': 2,
                'name': 'Guide Name',
                'price': 10000,
                'image': 'www.path/to/guide_image.jpg',
                'time_duration_in_min': 60
            },
            {
                'id': 3,
                'name': 'Guide Name',
                'price': 10000,
                'image': 'www.path/to/guide_image.jpg',
                'time_duration_in_min': 60
            }
        ],
        'tickets': {
            'is_ticketing_enabled': True,
            'adult_price': 10000,
            'child_price': 5000
        },
        'galleries': [
            {
                'id': 1,
                'name': 'Image Name',
                'is_from_wisnu_team': True,
                'is_vr_capable': True,
                'image': 'www.path/to/poi_image.jpg',
                'created_at': 'YMDTZ'
            },
            {
                'id': 2,
                'name': 'Image Name',
                'is_from_wisnu_team': True,
                'is_vr_capable': False,
                'image': 'www.path/to/poi_image.jpg',
                'created_at': 'YMDTZ'
            },
            {
                'id': 3,
                'name': 'Image Name',
                'is_from_wisnu_team': False,
                'is_vr_capable': False,
                'image': 'www.path/to/poi_image.jpg',
                'created_at': 'YMDTZ'
            }
        ]
    }

    response_data = {
        "status": 200,
        "message": "OK",
        "data": poi_data
    }

    return jsonify(response_data), 200

@app.route('/discover', methods=['GET'])
def discover():
    try:
        # Query the database to get the top-rated cities and POIs
        db_cursor.execute("""
            SELECT MIN(p.attraction_id) AS id, p.kota AS name, p.provinsi AS location, MIN(p.img) AS image, AVG(p.total_rating) AS total_rating
            FROM pois AS p
            WHERE p.total_rating <> 'None'
            GROUP BY p.kota, p.provinsi
            ORDER BY total_rating DESC
            LIMIT 3
        """)
        cities = db_cursor.fetchall()

        # Query the database to get the top-rated POIs
        db_cursor.execute("""
            SELECT p.attraction_id AS id, p.nama AS name, p.kota AS location, p.img AS image, p.total_rating AS total_rating
            FROM pois AS p
            WHERE p.total_rating <> 'None'
            ORDER BY p.total_rating DESC
            LIMIT 3
        """)
        poi = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "cities": cities,
                "poi": poi
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

@app.route('/poi', methods=['GET'])
def get_poi():
    try:
        # Get the category from the query parameters
        category = request.args.get('category')

        # Query the database to get the POIs based on the category
        db_cursor.execute("SELECT attraction_id, nama AS name, kota AS location, img AS image FROM pois WHERE category = %s", (category,))
        pois = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "size": len(pois),
            "page": 1,
            "data": pois
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
