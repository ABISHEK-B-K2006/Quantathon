from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

app = Flask(__name__)

# Initialize database (creates posts + users tables)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            text TEXT,
            timestamp TEXT,
            status TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Homepage form to post
@app.route('/')
def home():
    return '''
        <h2>Mini Social Media</h2>
        <form action="/post" method="post">
            Username: <input type="text" name="username"><br>
            Text: <input type="text" name="text"><br>
            <input type="submit" value="Post">
        </form>
        <hr>
        <a href="/users">View users</a>
    '''

# Post endpoint
@app.route('/post', methods=['POST'])
def post():
    username = request.form.get('username', '').strip()
    text = request.form.get('text', '').strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Pending"  # Detector will update this later

    if not username or not text:
        return "Provide username and text. <a href='/'>Back</a>"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO posts (username, text, timestamp, status) VALUES (?,?,?,?)",
              (username, text, timestamp, status))
    # Ensure user exists in users table (default Safe)
    c.execute("INSERT OR IGNORE INTO users (username, status) VALUES (?, ?)", (username, "✅ Safe"))
    conn.commit()
    conn.close()

    return f"Post submitted! <a href='/'>Back</a>"

# Simple route to view users
@app.route('/users')
def users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, status FROM users ORDER BY username")
    rows = c.fetchall()
    conn.close()
    out = "<h2>Users</h2><ul>"
    for u, s in rows:
        out += f"<li>{u} — {s}</li>"
    out += "</ul><a href='/'>Back</a>"
    return out

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
    
