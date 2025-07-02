from sqlalchemy import create_engine, Column, Integer, String, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import pandas as pd
from dotenv import load_dotenv
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recommender.db") # Default to SQLite for local dev

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Problem(Base):
    __tablename__ = "problems"
    id = Column(String, primary_key=True, index=True) 
    name = Column(String, index=True)
    rating = Column(Integer, nullable=True)
    tags = Column(JSON) 

def create_db_and_tables():
    Base.metadata.create_all(engine)

# Example to save problems to DB
def save_problems_to_db(problems_df: pd.DataFrame):
    db = SessionLocal()
    try:
        # Clear existing problems or handle updates
        db.query(Problem).delete()
        for _, row in problems_df.iterrows():
            problem = Problem(
                id=row['problem_id'],
                name=row['problem_name'],
                rating=row['problem_rating'],
                tags=row['problem_tags'].tolist() if isinstance(row['problem_tags'], np.ndarray) else row['problem_tags']
            )
            db.add(problem)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving problems to DB: {e}")
    finally:
        db.close()

def get_problems_from_db():
    db = SessionLocal()
    try:
        problems = db.query(Problem).all()
        return pd.DataFrame([
            {
                'problem_id': p.id,
                'problem_name': p.name,
                'problem_rating': p.rating,
                'problem_tags': p.tags
            } for p in problems
        ])
    finally:
        db.close()