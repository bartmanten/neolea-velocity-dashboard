import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = os.getenv("SPINS_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "spins.db"))
DB_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
