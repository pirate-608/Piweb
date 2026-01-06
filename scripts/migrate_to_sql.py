import os
import sys
import logging

# Ensure we can import from web directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import both the 'db' object and all Models to ensure they are registered
from app import app
from models import db, User, Question, ExamResult, UserCategoryStat, UserPermission

# Configure Logging
logging.basicConfig(level=logging.INFO, format='[Migration] %(message)s')
logger = logging.getLogger()

def migrate():
    """
    Migrate data from default SQLite (in app.config) to a target database defined by NEW_DB_URI env var.
    """
    target_uri = os.environ.get('NEW_DB_URI')
    if not target_uri:
        logger.error("Please set 'NEW_DB_URI' environment variable to the target database connection string.")
        logger.error("Example: postgresql://postgres:password@localhost:5432/grading_db")
        return

    # 1. Access Source Data (SQLite) using the existing Flask App context
    logger.info("Reading data from source database (SQLite)...")
    
    source_data = {}
    
    with app.app_context():
        # Validate source DB
        if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
            logger.warning(f"Current app config is NOT SQLite: {app.config['SQLALCHEMY_DATABASE_URI']}")
            logger.warning("Continuing anyway...")

        # Read all data into memory
        # We assume the dataset fits in memory (reasonable for text/grading systems)
        source_data['users'] = User.query.all()
        source_data['questions'] = Question.query.all()
        source_data['results'] = ExamResult.query.all()
        source_data['categories'] = UserCategoryStat.query.all()
        source_data['permissions'] = UserPermission.query.all()
        
        # Detach objects from session so they can be added to a new session
        for key in source_data:
            for item in source_data[key]:
                db.session.expunge(item)
                
        logger.info(f"Loaded: {len(source_data['users'])} Users, {len(source_data['questions'])} Questions, {len(source_data['results'])} Results.")

    # 2. Connect to Target Database
    logger.info(f"Connecting to target database: {target_uri}")
    target_engine = create_engine(target_uri)
    TargetSession = sessionmaker(bind=target_engine)
    target_session = TargetSession()

    try:
        # 3. Create Tables in Target
        # We reuse the metadata from 'db' logic, but bind it to target engine
        logger.info("Creating tables in target database...")
        db.metadata.create_all(target_engine)

        # 4. Insert Data
        logger.info("Migrating data...")
        
        # Order matters due to Foreign Keys!
        # User -> Question -> Others
        
        # Users
        for u in source_data['users']:
            target_session.merge(u) # merge handles primary key preservation better than add
        target_session.flush() # Ensure IDs are booked
        
        # Questions
        for q in source_data['questions']:
            target_session.merge(q)
            
        # ExamResults (references User)
        for r in source_data['results']:
            target_session.merge(r)

        # UserCategoryStat (references User)
        for s in source_data['categories']:
            target_session.merge(s)
            
        # UserPermission (references User)
        for p in source_data['permissions']:
            target_session.merge(p)

        target_session.commit()
        logger.info("Migration successful! All data copied.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        target_session.rollback()
    finally:
        target_session.close()

if __name__ == "__main__":
    migrate()
