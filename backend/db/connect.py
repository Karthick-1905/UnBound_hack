import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5433'),
        dbname=os.getenv('DB_NAME', 'unbound_db'),
        user=os.getenv('DB_USER', 'unbound_user'),
        password=os.getenv('DB_PASSWORD', 'unbound_password')
    )

