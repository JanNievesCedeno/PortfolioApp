import psycopg2
from psycopg2.extras import RealDictCursor
import os
from flask import g

# Database URL from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    """Get database connection for current request"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return db

def get_cursor():
    """Get cursor for database operations"""
    return get_db().cursor()

def close_db(exception=None):
    """Close database connection after request"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()