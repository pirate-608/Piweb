import os
import time
import psycopg2
from urllib.parse import urlparse
import sys

def wait_for_db():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not set, skipping wait.")
        return

    print(f"Waiting for database at {db_url.split('@')[-1]}...")
    
    # Simple retry logic
    max_retries = 30
    for i in range(max_retries):
        try:
            # Parse the URL to get parameters for psycopg2
            result = urlparse(db_url)
            username = result.username
            password = result.password
            database = result.path[1:]
            hostname = result.hostname
            port = result.port
            
            conn = psycopg2.connect(
                dbname=database,
                user=username,
                password=password,
                host=hostname,
                port=port
            )
            conn.close()
            print("Database is ready!")
            return
        except Exception as e:
            print(f"Database not ready yet... ({e})")
            time.sleep(2)
            
    print("Could not connect to database after many retries.")
    sys.exit(1)

if __name__ == "__main__":
    wait_for_db()
