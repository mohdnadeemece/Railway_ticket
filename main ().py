import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    # Create and configure the app
    app = Flask(__name__)
    
    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "a-default-secret-key")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize database and migrations
    db.init_app(app)
    migrate.init_app(app, db)
    
    return app

app = create_app()

# Import models after app is created
import models

# Import routes - this is important to register all the routes
from app import *

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)