import os
import sys
import json

# Prevent implicit DB initialization on import
os.environ['SKIP_INIT_DB'] = 'true'

# Add web directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web'))

from app import app, db
from models import User, Question, ExamResult, UserCategoryStat, UserPermission, SystemSetting
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, make_transient

def get_sqlite_data():
    """Read all data from current SQLite database using a standalone engine"""
    data = {}
    
    # Force SQLite URI to ensure we read from the source file
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sqlite_path = os.path.join(project_root, 'web', 'instance', 'data.db')
    
    # Handle Windows paths for URI
    sqlite_uri = f'sqlite:///{sqlite_path.replace(os.sep, "/")}'
    
    print(f"Reading data from SQLite: {sqlite_uri}")
    
    if not os.path.exists(sqlite_path):
        print(f"Error: SQLite database not found at {sqlite_path}")
        return data

    # Create isolated engine/session for SQLite read
    engine = create_engine(sqlite_uri)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        data['users'] = session.query(User).all()
        data['questions'] = session.query(Question).all()
        data['results'] = session.query(ExamResult).all()
        data['stats'] = session.query(UserCategoryStat).all()
        data['perms'] = session.query(UserPermission).all()
        data['settings'] = session.query(SystemSetting).all()
        
        # Expunge to detach from this session so they can be added to another
        session.expunge_all()
        
        # Make transient explicitly (though expunge might be enough, make_transient clears session keys)
        for category in data.values():
            for item in category:
                make_transient(item)
                
        print(f"Loaded: {len(data['users'])} users, {len(data['questions'])} questions.")
    except Exception as e:
        print(f"Error reading from SQLite: {e}")
    finally:
        session.close()

    return data

def save_to_postgres(data, pg_uri):
    """Save data to Postgres"""
    print(f"Connecting to Postgres: {pg_uri}")
    
    # Configure app to use Postgres
    app.config['SQLALCHEMY_DATABASE_URI'] = pg_uri
    
    with app.app_context():
        print("Creating tables in Postgres...")
        try:
            # Drop all tables first to ensure clean state and schema updates
            db.drop_all()
            db.create_all()
        except Exception as e:
            print(f"Error creating tables: {e}")
            return

        print("Migrating Users...")
        for u in data['users']:
            db.session.merge(u) # merge handles primary key conflicts/existence
        
        print("Migrating Questions...")
        for q in data['questions']:
            db.session.merge(q)

        print("Migrating Results (this may take a while)...")
        for r in data['results']:
            db.session.merge(r)
            
        print("Migrating Stats...")
        for s in data['stats']:
            db.session.merge(s)
            
        print("Migrating Permissions...")
        for p in data['perms']:
            db.session.merge(p)
            
        print("Migrating Settings...")
        for s in data['settings']:
            db.session.merge(s)

        try:
            db.session.commit()
            print("Migration completed successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error saving to Postgres: {e}")

if __name__ == "__main__":
    # 1. Get Target DB URI
    default_pg = "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
    print("="*60)
    print(" SQLite to PostgreSQL Migration Tool")
    print("="*60)
    print("Ensure your Postgres container is running.")
    print(f"Default URI: {default_pg}")
    
    target_uri = input(f"Enter PostgreSQL URI (Press Enter to use default): ").strip()
    if not target_uri:
        target_uri = default_pg
        
    # 2. Extract
    sqlite_data = get_sqlite_data()
    
    # 3. Load
    save_to_postgres(sqlite_data, target_uri)
