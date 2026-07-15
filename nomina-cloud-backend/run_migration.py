import psycopg2
import sys

db_url = "postgresql://postgres:Un1f1k4*2026@db.esruqpxrvclwjekrssom.supabase.co:5432/postgres"


def run_migration():
    try:
        with open('supabase_schema.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()

        print("Conectando a la base de datos...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()

        print("Ejecutando script SQL...")
        cursor.execute(sql_script)

        print("Migración completada: Las tablas se han creado exitosamente en Supabase.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error durante la migración: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
