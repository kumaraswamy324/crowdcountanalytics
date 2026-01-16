import sqlite3

DB_NAME = "database.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Get column names
cursor.execute("PRAGMA table_info(users);")
columns = [col[1] for col in cursor.fetchall()]

# Get data
cursor.execute("SELECT * FROM users;")
rows = cursor.fetchall()

# Print header
print("\nUSERS TABLE\n")
print(" | ".join(columns))
print("-" * (len(" | ".join(columns)) + 10))

# Print rows
if not rows:
    print("No data found.")
else:
    for row in rows:
        print(" | ".join(str(item) for item in row))

conn.close()
