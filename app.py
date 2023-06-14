import datetime
from flask import Flask, request, jsonify
import jwt
import mysql.connector
import os
import bcrypt
import random
from dotenv import load_dotenv
from functools import wraps
from ml.itinerary.itinerary import generate_itinerary
from ml.guides.guides import guides_recommendation

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
        db_cursor.fetchall()

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
        db_cursor.fetchall()

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
@jwt_required
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

@app.route('/pois', methods=['GET'])
@jwt_required
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

@app.route('/event/<int:id>', methods=['GET'])
@jwt_required
def get_event_detail(id):
    try:
        # Retrieve event detail from the database based on the provided ID
        query = "SELECT attraction_id, nama AS name, description, kota AS location, img AS image, date FROM events WHERE attraction_id = %s"
        db_cursor.execute(query, (id,))
        event = db_cursor.fetchone()

        if event:
            # Format the response data
            response_data = {
                "status": 200,
                "message": "OK",
                "data": {
                    "id": event['attraction_id'],
                    "name": event['name'],
                    "description": event['description'],
                    "location": event['location'],
                    "image": event['image'],
                    "date": event['date']
                }
            }
            return jsonify(response_data), 200
        else:
            # Event not found
            response_data = {
                "status": 404,
                "message": "Event not found",
                "data": None
            }
            return jsonify(response_data), 404
    except Exception as e:
        # Error occurred
        response_data = {
            "status": 500,
            "message": str(e),
            "data": None
        }
        return jsonify(response_data), 500

@app.route('/events', methods=['GET'])
@jwt_required
def get_events():
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
        sql_query = "SELECT attraction_id AS id, nama AS name, kota AS location, img AS image FROM events"

        # Add ORDER BY clause to sort by date in ascending order
        sql_query += " ORDER BY date ASC"

        query_params = ()
        if limit is not None:
            sql_query += " LIMIT %s"
            query_params += (limit,)
        if offset is not None:
            sql_query += " OFFSET %s"
            query_params += (offset,)

        # Execute the SQL query
        db_cursor.execute(sql_query, query_params)
        events = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "preview": preview,
            "size": size,
            "page": page,
            "data": events
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

@app.route('/search', methods=['POST'])
@jwt_required
def search():
    try:
        # Get the keyword and filter from the request form data
        keyword = request.form.get('keyword')
        category_filter = request.form.get('filter')

        # Set the default filter value to "all" if it is empty
        if not category_filter:
            category_filter = 'all'

        # Query the database to search for cities and POIs based on the keyword and category filter
        city_query = """
            SELECT DISTINCT attraction_id AS id, kota AS name, provinsi AS location
            FROM pois
            WHERE (kota LIKE %s OR provinsi LIKE %s)
        """

        poi_query = """
            SELECT attraction_id AS id, nama AS name, kota AS location, img AS image
            FROM pois
            WHERE (nama LIKE %s OR kota LIKE %s)
        """

        # Add the keyword parameter to the query parameters
        city_query_params = ('%' + keyword + '%', '%' + keyword + '%')
        poi_query_params = ('%' + keyword + '%', '%' + keyword + '%')

        # Add the category filter to the query parameters and queries if it's not 'all'
        if category_filter != 'all':
            city_query += " AND category = %s"
            poi_query += " AND category = %s"
            city_query_params += (category_filter,)
            poi_query_params += (category_filter,)

        # Execute the SQL query to search for cities
        db_cursor.execute(city_query, city_query_params)
        cities = db_cursor.fetchall()

        # Remove items with duplicated name values
        unique_cities = []
        city_names = set()
        for city in cities:
            if city['name'] not in city_names:
                unique_cities.append(city)
                city_names.add(city['name'])

        # Execute the SQL query to search for POIs
        db_cursor.execute(poi_query, poi_query_params)
        pois = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "cities": unique_cities,
                "poi": pois
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

@app.route('/discover', methods=['GET'])
@jwt_required
def discover():
    try:
        # Query the database to get the top-rated cities and POIs
        db_cursor.execute("""
            SELECT MIN(p.id_kota) AS id, p.kota AS name, p.provinsi AS location, MIN(p.img) AS image, AVG(p.total_rating) AS total_rating
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
@jwt_required
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

@app.route('/poi/<int:id>', methods=['GET'])
@jwt_required
def get_poi_data(id):
    try:
        # Query the database to get the POI detail based on the provided ID
        query = "SELECT attraction_id, nama AS name, kota AS location, img AS image FROM pois WHERE attraction_id = %s"
        db_cursor.execute(query, (id,))
        poi = db_cursor.fetchone()

        if poi:
            if poi['image'] == "None":
                poi['image'] = 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/18/81/38/b5/saloka-memiliki-25-wahana.jpg?w=500&h=-1&s=1,110.458481,-7.2803431'
            # Format the response data
            response_data = {
                "status": 200,
                "message": "OK",
                "data": {
                    "id": poi['attraction_id'],
                    "name": poi['name'],
                    "location": poi['location'],
                    "image": poi['image'],
                    # "long": poi['long'],
                    # "lat": poi['lat'],
                    
                    
                }
            }
            return jsonify(response_data), 200
        else:
            # POI not found
            response_data = {
                "status": 404,
                "message": "POI not found",
                "data": None
            }
            return jsonify(response_data), 404
    except Exception as e:
        # Error occurred
        response_data = {
            "status": 500,
            "message": str(e),
            "data": None
        }
        return jsonify(response_data), 500


@app.route('/cities', methods=['GET'])
@jwt_required
def get_cities():
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
        sql_query = "SELECT id_kota AS id, kota AS name, provinsi AS location, CONCAT('The ', kota, ' city is located at ', provinsi, '. Visit this city for your next holiday. #WisataNusantara') AS description, img AS image FROM pois"

        # Add GROUP BY clause to group by city name
        sql_query += " GROUP BY name"

        # Add ORDER BY clause to sort by id_kota in ascending order
        sql_query += " ORDER BY id_kota ASC"

        query_params = ()
        if limit is not None:
            sql_query += " LIMIT %s"
            query_params += (limit,)
        if offset is not None:
            sql_query += " OFFSET %s"
            query_params += (offset,)

        # Execute the SQL query
        db_cursor.execute(sql_query, query_params)
        cities = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "preview": preview,
            "size": size,
            "page": page,
            "data": cities
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
@jwt_required
def get_itinerary(city_id):
    try:
        # Query the database to get the city name based on the city_id
        db_cursor.execute("SELECT kota FROM pois WHERE id_kota = %s", (city_id,))
        result = db_cursor.fetchone()
        db_cursor.fetchall()

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

        guides_recommendations_raw = guides_recommendation(city_name).to_dict('records')
        guides_recommendations = []

        # Apparently, the mobile app can't handle generated images, 
        # so we'll use a list of images instead
        guides_image_male = [
            "https://xsgames.co/randomusers/assets/avatars/male/43.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/37.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/24.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/38.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/70.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/35.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/69.jpg"
        ]
        guides_image_female = [
            "https://xsgames.co/randomusers/assets/avatars/female/52.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/27.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/71.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/8.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/10.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/67.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/77.jpg"
        ]
        for guide in guides_recommendations_raw:
            # Strip PMD prefix from guide_id
            guide_id = guide['Pemandu_ID'][3:]

            # Determine the image list based on the gender
            image_list = guides_image_female if "female" in guide['Avatars'] else guides_image_male

            # Get a random image from the list
            random_image = random.choice(image_list)

            guides_recommendations.append({
                "id": guide_id,
                "name": guide['Nama_Pemandu'],
                "price": guide['Price_per_hour'],
                "image": random_image,
                "time_duration_in_min": guide['Time_duration_in_min']
            })

        # Divide the itinerary data into an array of days
        itinerary_per_day = []
        for day in range(1, num_days + 1):
            poi_per_day = []
            for poi in itinerary_data:
                if poi['hari'] == day:
                    if type(poi['img']) == float:
                        poi['img'] = 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/18/81/38/b5/saloka-memiliki-25-wahana.jpg?w=500&h=-1&s=1,110.458481,-7.2803431'
                    poi_data = {
                        "id": poi['attraction_id'],
                        "name": poi['nama'],
                        "location": poi['kota'],
                        "image": poi['img'],
                        "tickets": {
                            "is_ticketing_enabled": True,
                            "adult_price": poi['adult_price'],
                            "child_price": poi['child_price']
                        },
                        "guides": guides_recommendations
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

    except Exception as e:
        # Server error
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500

@app.route('/city/<int:city_id>', methods=['GET'])
@jwt_required
def get_city(city_id):
    try:
        # Build the SQL query to fetch the city details
        city_query = "SELECT id_kota AS id, kota AS name, provinsi AS location, CONCAT('The ', kota, ' city is located at ', provinsi, '. Visit this city for your next holiday. #WisataNusantara') AS description, img AS image FROM pois WHERE id_kota = %s"

        # Execute the SQL query to fetch the city details
        db_cursor.execute(city_query, (city_id,))
        city = db_cursor.fetchone()

        if city is None:
            # City not found
            response_data = {
                "status": 404,
                "message": "City not found",
                "data": None
            }
            return jsonify(response_data), 404

        # Build the SQL query to fetch the POIs for the city
        poi_query = "SELECT attraction_id AS id, nama AS name, kota AS location, img AS image FROM pois WHERE id_kota = %s"

        # Execute the SQL query to fetch the POIs for the city
        db_cursor.execute(poi_query, (city_id,))
        pois = db_cursor.fetchall()

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "id": city["id"],
                "name": city["name"],
                "location": city["location"],
                "description": city["description"],
                "image": city["image"],
                "poi": pois
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

@app.route('/guide/<int:guide_id>', methods=['GET'])
@jwt_required
def guide_detail(guide_id):
    try:
        if guide_id < 1000:
            guide_id = "PMD" + str(guide_id).zfill(3)
        else:
            guide_id = "PMD" + str(guide_id)
        # Query the database to get the guide information based on the guide_id
        db_cursor.execute("SELECT * FROM guides WHERE Pemandu_ID = %s", (guide_id,))
        guide = db_cursor.fetchone()

        if not guide:
            # Guide not found
            response_data = {
                "status": 404,
                "message": "Guide not found",
                "data": None
            }
            return jsonify(response_data), 404

        # Query the database to get the reviews for the guide
        db_cursor.execute("SELECT * FROM reviews WHERE Pemandu_ID = %s", (guide_id,))
        reviews = db_cursor.fetchall()

        # Apparently, the mobile app can't handle generated images, 
        # so we'll use a list of images instead
        guides_image_male = [
            "https://xsgames.co/randomusers/assets/avatars/male/43.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/37.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/24.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/38.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/70.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/35.jpg",
            "https://xsgames.co/randomusers/assets/avatars/male/69.jpg"
        ]
        guides_image_female = [
            "https://xsgames.co/randomusers/assets/avatars/female/52.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/27.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/71.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/8.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/10.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/67.jpg",
            "https://xsgames.co/randomusers/assets/avatars/female/77.jpg"
        ]

        # Determine the image list based on the gender
        image_list = guides_image_female if "female" in guide['Avatars'] else guides_image_male

        # Get a random image from the list
        random_image = random.choice(image_list)

        # Create the response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "id": guide['Pemandu_ID'],
                "name": guide['Nama_Pemandu'],
                "price": guide['Price_per_hour'],
                "image": random_image,
                "time_duration_in_min": guide['Time_duration_in_min'],
                "avg_star": guide['Rating'],
                "reviews": []
            }
        }

        # Array of 50 random names
        random_names = [
            "John", "Alice", "Michael", "Emily", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Emma",
            "Andrew", "Ava", "Ryan", "Mia", "Christopher", "Isabella", "Ethan", "Charlotte", "Joshua", "Amelia",
            "William", "Harper", "Joseph", "Evelyn", "James", "Abigail", "Benjamin", "Elizabeth", "Samuel", "Sofia",
            "Jacob", "Ella", "Alexander", "Avery", "Henry", "Grace", "Jackson", "Scarlett", "Sebastian", "Victoria",
            "Aiden", "Chloe", "Luke", "Lily", "Carter", "Zoe", "Jayden", "Madison", "Gabriel", "Layla"
        ]

        # Shuffle the array of names
        random.shuffle(random_names)

        # Add the reviews to the response data
        for review in reviews:
            response_data['data']['reviews'].append({
                "id": review['User_ID'],
                "name": random_names.pop(),
                "review": review['Review'],
                "star": review['Rating']
            })

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


@app.route('/transaction/new', methods=['POST'])
@jwt_required
def create_order():
    try:

        # Inisialisasi variabel order_id
        order_id = None

        # Get the request body
        request_data = request.get_json()

        query = """
            INSERT INTO transactions (id, is_guide_order, is_ticket_order, price, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        # Extract ticket and guide data from the request
        ticket_data = request_data.get('ticket', [])
        guide_data = request_data.get('guide')
        is_guide_order = True  # Ubah nilai sesuai logika bisnis
        is_ticket_order = False  # Ubah nilai sesuai logika bisnis
        price = request_data.get('transactions')  # Ubah nilai sesuai logika bisnis
        created_at = datetime.datetime.now()
        
        # Perform order creation logic here
        # Simpan data transaksi ke database
        # Ganti bagian ini dengan operasi database yang sesuai untuk menyimpan data ke tabel 'transactions'
        

        db_cursor.execute(query, (order_id, is_guide_order, is_ticket_order, price, created_at))
        db_connection.commit()            

        
        # Process ticket data
        tickets = []
        for ticket in ticket_data:
        # Generate a random order ID
            order_id = random.randint(1, 1000)
            poi_id = ticket['poi_id']
            num_adult = ticket['num_adult']
            num_child = ticket['num_child']

            
            # Retrieve POI information from the database based on poi_id
            poi_query = """
                SELECT attraction_id as id, nama as name, kota as location, adult_price, child_price FROM pois WHERE attraction_id = %s
            """
            
            poi_params = (poi_id,)
            db_cursor.execute(poi_query, poi_params)
            poi_row = db_cursor.fetchone()

            
            # Perform ticket processing logic here
            
            # Generate ticket details
            ticket_details = {
                "id": order_id,
                "poi": {
                    "id": poi_id,
                    "name": poi_row['name'],
                    "location": poi_row['location']
                },
                "valid_date": (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),  # Valid for 30 days from ticket creation
                "adult": [],
                "child": []
            }
            
            adult_price = poi_row['adult_price']
            child_price = poi_row['child_price']

            # Add adult tickets
            for i in range(num_adult):
                ticket_details['adult'].append({
                    "name": f"Ticket Buyer {i+1}",
                    "price": adult_price
                })
            
            # Add child tickets
            for i in range(num_child):
                ticket_details['child'].append({
                    "name": f"Ticket Buyer {i+1} - child",
                    "price": child_price
                })
            
            # Add ticket details to the tickets list
            tickets.append(ticket_details)

                        # Insert ticket data into the 'tickets' table
            ticket_query = """
                INSERT INTO tickets (id, is_active, poi_id, created_at)
                VALUES (%s, %s, %s, %s)
            """

            ticket_params = (ticket_details['id'], 1, poi_id, created_at)
            db_cursor.execute(ticket_query, ticket_params)
            db_connection.commit()

        # Process guide data
        guide = None
        if guide_data:
            poi_id = guide_data['poi_id']
            guide_id = guide_data['guide_id']
            min_multiplier = guide_data['min_multiplier']
            
        # Generate response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "id": order_id,  # Replace with the actual order ID
                "ticket": tickets,  # Replace with the actual ticket data
                "guide": None,  # Replace with the actual guide data
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Replace with the actual creation timestamp
            }
        }

        # Return the response as JSON
        return jsonify(response_data), response_data['status']
    except Exception as e:
        # Server error
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500
    
@app.route('/transactions', methods=['GET'])
@jwt_required
def list_transactions():
    try:
        filter_type = request.args.get('filter', 'all')  # Get the filter parameter, default to 'all' if not provided

        # Construct the SQL query based on the filter type
        if filter_type == 'guide':
            query = """
                SELECT * FROM transactions
                WHERE is_guide_order = true
            """
        elif filter_type == 'ticket':
            query = """
                SELECT * FROM transactions
                WHERE is_ticket_order = true
            """
        else:
            query = """
                SELECT * FROM transactions
            """

        # Execute the SQL query
        db_cursor.execute(query)

        # Fetch the results
        results = db_cursor.fetchall()

        # Process the results
        transactions = []
        for row in results:
            transaction = {
                "id": row['id'],
                "is_guide_order": row['is_guide_order'] == 1,
                "is_ticket_order": row['is_ticket_order'] == 1,
                "price": row['price'],
                "created_at": row['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            }
            transactions.append(transaction)

        # Generate response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": transactions
        }

        return jsonify(response_data), response_data['status']
    except Exception as e:
        # Error occurred during transaction listing
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500    

@app.route('/tickets', methods=['GET'])
@jwt_required
def list_tickets():
    try:
        filter_type = request.args.get('filter', 'active')  # Get the filter parameter, default to 'active' if not provided

        # Construct the SQL query based on the filter type
        if filter_type == 'active':
            query = """
                SELECT * FROM tickets
                WHERE is_active = true
            """
        elif filter_type == 'expired':
            query = """
                SELECT * FROM tickets
                WHERE is_active = false
            """
        else:
            query = """
                SELECT * FROM tickets
            """

        # Execute the SQL query
        db_cursor.execute(query)

        # Fetch the results
        results = db_cursor.fetchall()

            
        # Process the results
        tickets = []
        for row in results:
            poi_id = row['poi_id']
            # Retrieve POI information from the database based on poi_id
            poi_query = """
                SELECT attraction_id as id, nama as name, kota as location FROM pois WHERE attraction_id = %s
            """
            
            poi_params = (poi_id,)
            db_cursor.execute(poi_query, poi_params)
            poi_row = db_cursor.fetchone()

            # Check if poi_row is None
            if poi_row is None:
                # Handle case when no matching POI is found
                poi_row = {
                    "id": None,
                    "name": None,
                    "location": None
                }

            ticket = {
                "id": row['id'],
                "is_active": row['is_active'] == 1,
                "poi": {
                    "id": poi_row['id'],
                    "name": poi_row['name'],
                    "location": poi_row["location"]
                },
                "created_at": row['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            }
            tickets.append(ticket)

        # Generate response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": tickets
        }

        return jsonify(response_data), response_data['status']
    except Exception as e:
        # Error occurred during ticket listing
        response_data = {
            "status": 500,
            "message": f"Reason: {str(e)}",
            "data": None
        }
        return jsonify(response_data), 500

@app.route('/ticket/<string:ticket_id>', methods=['GET'])
@jwt_required
def get_ticket(ticket_id):
    try:
        # Construct the SQL query to retrieve ticket details based on ticket_id
        query = """
            SELECT * FROM tickets WHERE id = %s
        """
        params = (ticket_id,)
        db_cursor.execute(query, params)

        # Fetch the result
        ticket = db_cursor.fetchone()

        # Check if ticket is None
        if ticket is None:
            response_data = {
                "status": 404,
                "message": "Ticket not found",
                "data": None
            }
            return jsonify(response_data), 404

        # Retrieve POI information from the database based on poi_id
        poi_query = """
            SELECT attraction_id as id, nama as name, kota as location FROM pois WHERE attraction_id = %s
        """
        poi_params = (ticket['poi_id'],)
        db_cursor.execute(poi_query, poi_params)
        poi_row = db_cursor.fetchone()

        # Check if poi_row is None
        if poi_row is None:
            # Handle case when no matching POI is found
            poi_row = {
                "id": None,
                "name": None,
                "location": None
            }

        # Generate response data
        response_data = {
            "status": 200,
            "message": "OK",
            "data": {
                "id": ticket['id'],
                "poi": {
                    "id": poi_row['id'],
                    "name": poi_row['name'],
                    "location": poi_row["location"]
                },
                "valid_date": (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"), 
                # ticket['valid_date'].strftime("%Y-%m-%d"),
                "adult": [
                    {
                        "name": "Ticket Buyer 1",
                        "price": 10000
                    },
                    {
                        "name": "Ticket Buyer 2",
                        "price": 10000
                    }
                ],
                "child": [
                    {
                        "name": "Ticket Buyer 1 - child",
                        "price": 5000
                    }
                ],
                "total_price": 25000,
                "created_at": ticket['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        return jsonify(response_data), response_data['status']
    except Exception as e:
        # Error occurred during ticket retrieval
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
    app.run(host='0.0.0.0', port=80)
