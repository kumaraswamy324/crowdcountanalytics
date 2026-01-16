import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password TEXT,
    place TEXT,
    dob TEXT
)
""")

conn.commit()
conn.close()

print("Database created successfully")
