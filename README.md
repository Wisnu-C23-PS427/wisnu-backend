# wisnu-backend

## How to run

1. Clone this repository

```bash
git clone https://github.com/mufidu/wisnu-backend.git
cd wisnu-backend
```

2. Set up the environment

```bash
cd wisnu-backend

# Optional: Create virtual environment
pip install virtualenv
virtualenv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

3. Create .env file based on .env.example

4. Run the server

```bash
flask run
```

Server will run on port 5000

5. (Optional) Deploy to Google App Engine

```bash
gcloud app deploy
```
