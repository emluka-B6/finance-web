import sqlite3
from extensions import ALREADY_ADDED, DB_ERROR, DB_SUCCESS

class DirectDb():
    def _get_db_connection(__self__):
        conn = sqlite3.connect('instance/sqlite.db')
        conn.row_factory = sqlite3.Row
        return conn

    def create(__self__, flaskApp):
        # Create a table if it doesn't exist
        conn = __self__._get_db_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def getUsers(__self__):
        conn = __self__._get_db_connection()
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()
        return users
        
    def addUser(__self__, name, email):
        conn = __self__._get_db_connection()
        state = DB_SUCCESS
        eroor = None

        cursor = conn.cursor()
        # Check if the user already exists
        #cursor.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        existing_user_by_mail = cursor.fetchone()
        cursor.execute('SELECT * FROM users WHERE name = ?', (name,))
        existing_user = cursor.fetchone()

        if existing_user or existing_user_by_mail:
            state = ALREADY_ADDED
            conn.close()
            return state, eroor

        # Add the new user
        try:
            cursor.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
            conn.commit()
        except sqlite3.Error as e:
            state = DB_ERROR
            eroor = e
        finally:
            conn.close()

        return state, eroor
    
    def deleteUser(__self__, user_id):
        conn = __self__._get_db_connection()
        state = DB_SUCCESS
        eroor = None
        try:
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
        except sqlite3.Error as e:
            state = DB_ERROR
            eroor = e
        finally:
            conn.close()

        return state, eroor