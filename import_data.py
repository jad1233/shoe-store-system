import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "store.db"
IMPORT_DIR = BASE_DIR / "import"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def import_users(conn):
    df = pd.read_excel(IMPORT_DIR / "user_import.xlsx")

    role_map = {
        "Администратор": "admin",
        "Менеджер": "manager",
        "Авторизированный клиент": "client",
    }

    for _, row in df.iterrows():
        role_name = role_map.get(row["Роль сотрудника"], "client")

        role_id = conn.execute(
            "SELECT id FROM roles WHERE name=?", (role_name,)
        ).fetchone()[0]

        conn.execute(
            """
        INSERT INTO users(full_name, login, password, role_id)
        VALUES (?, ?, ?, ?)
        """,
            (row["ФИО"], row["Логин"], row["Пароль"], role_id),
        )


def import_products(conn):
    df = pd.read_excel(IMPORT_DIR / "Tovar.xlsx")

    for _, row in df.iterrows():

        category = row["Категория товара"]
        manufacturer = row["Производитель"]
        supplier = row["Поставщик"]

        conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (category,))
        conn.execute(
            "INSERT OR IGNORE INTO manufacturers(name) VALUES (?)", (manufacturer,)
        )
        conn.execute("INSERT OR IGNORE INTO suppliers(name) VALUES (?)", (supplier,))

        category_id = conn.execute(
            "SELECT id FROM categories WHERE name=?", (category,)
        ).fetchone()[0]
        manufacturer_id = conn.execute(
            "SELECT id FROM manufacturers WHERE name=?", (manufacturer,)
        ).fetchone()[0]
        supplier_id = conn.execute(
            "SELECT id FROM suppliers WHERE name=?", (supplier,)
        ).fetchone()[0]

        conn.execute(
            """
        INSERT INTO products(
        article,name,unit,price,
        supplier_id,manufacturer_id,category_id,
        discount_percent,quantity,description,
        photo_filename,image_path)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                row["Артикул"],
                row["Наименование товара"],
                row["Единица измерения"],
                row["Цена"],
                supplier_id,
                manufacturer_id,
                category_id,
                row["Действующая скидка"],
                row["Кол-во на складе"],
                row["Описание товара"],
                row["Фото"],
                f"resources/{row['Фото']}",
            ),
        )


def import_pickup_points(conn):
    df = pd.read_excel(IMPORT_DIR / "Пункты выдачи_import.xlsx", header=None)

    for _, row in df.iterrows():
        conn.execute("INSERT INTO pickup_points(address) VALUES (?)", (row[0],))


def main():
    conn = connect()

    print("Importing users...")
    import_users(conn)

    print("Importing products...")
    import_products(conn)

    print("Importing pickup points...")
    import_pickup_points(conn)

    conn.commit()
    conn.close()

    print("✅ Import finished successfully")


if __name__ == "__main__":
    main()
