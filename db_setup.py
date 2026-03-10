import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "store.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def create_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)

    # roles (as in task: guest/client/manager/admin)
    conn.executemany(
        "INSERT OR IGNORE INTO roles(name) VALUES (?)",
        [("guest",), ("client",), ("manager",), ("admin",)],
    )

    conn.commit()
    conn.close()
    print("✅ DB created:", DB_PATH)

if __name__ == "__main__":
    create_db()