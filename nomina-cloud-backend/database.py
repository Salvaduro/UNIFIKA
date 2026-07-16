import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv

# Intentar cargar .env.local primero, luego .env como fallback.
# En Render, esto no hará nada y las variables se tomarán del sistema operativo.
load_dotenv(".env.local")
load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No se encontró DATABASE_URL en el entorno (OS) ni en los archivos .env / .env.local")

# Creación del engine de SQLAlchemy
engine = create_engine(DATABASE_URL)

# Sesión local para interactuar con la DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos (si los creamos más adelante con ORM)
Base = declarative_base()

# Dependencia para obtener la sesión de BD en cada request de FastAPI


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
