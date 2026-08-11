import os

from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError

from schema.schema_discovery import discover_schema


load_dotenv()

connection_string = os.getenv("DATABASE_URL")

if not connection_string:
    raise SystemExit(
        "Set DATABASE_URL in .env or your shell, for example:\n"
        "DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/pagila"
    )

try:
    schema = discover_schema(connection_string)
except OperationalError as exc:
    raise SystemExit(
        "Could not connect to the database. Check the username, password, host, "
        f"port, and database name in DATABASE_URL.\nOriginal error: {exc.orig}"
    ) from exc


print(schema)

for table_name, table in schema.items():
    print("\nTABLE:", table_name)

    print("columns:")
    for col in table.columns:
        print(f" - {col.name}: {col.datatype}")

    print("Primary Keys:", table.primary_keys)

    print("Foreign Keys:")
    for fk in table.foreign_keys:
        print(f" - {fk.column} -> {fk.ref_table}.{fk.ref_column}")
