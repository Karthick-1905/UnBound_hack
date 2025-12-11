import psycopg2
import os

# Database connection parameters (match docker-compose.yml)
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5433')
DB_NAME = os.getenv('DB_NAME', 'unbound_db')
DB_USER = os.getenv('DB_USER', 'unbound_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'unbound_password')

def create_tables():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    with open('db/schema.sql', 'r') as f:
        sql = f.read()
    
    cursor.execute(sql)
    conn.commit()
    cursor.close()
    conn.close()
    print("Database tables created successfully.")

if __name__ == "__main__":
    create_tables()