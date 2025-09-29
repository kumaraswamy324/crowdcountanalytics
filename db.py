import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sanjusql#324",
        database="crowdcount_auth",
    )
