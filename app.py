from flask import Flask, request, render_template, redirect, url_for
import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

app = Flask(__name__)

# Initialize database
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

# Homepage feed + form
@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, text, timestamp, status FROM posts ORDER BY id DESC")
    posts = c.fetchall()
    conn.close()
    return render_template("home.html", posts=posts)

# Post endpoint
@app.route('/post', methods=['POST'])
def post():
    username = request.form.get('username', '').strip()
    text = request.form.get('text', '').strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Pending"

    if not username or not text:
        return redirect(url_for("home"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO posts (username, text, timestamp, status) VALUES (?,?,?,?)",
              (username, text, timestamp, status))
    c.execute("INSERT OR IGNORE INTO users (username, status) VALUES (?, ?)", (username, "✅ Safe"))
    conn.commit()
    conn.close()

    return redirect(url_for("home"))

# Users list
@app.route('/users')
def users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, status FROM users ORDER BY username")
    rows = c.fetchall()
    conn.close()
    return render_template("users.html", users=rows)

# 🔎 Search for a user (directly go to profile)
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('username', '').strip()
    if not query:
        return redirect(url_for("home"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username=?", (query,))
    row = c.fetchone()
    conn.close()

    if not row:
        return f"<h3>No such user found</h3><a href='/'>Back</a>"

    return redirect(url_for("profile", username=query))

# 👤 Profile page
@app.route('/profile/<username>')
def profile(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Fetch posts
    c.execute("SELECT text, timestamp, status FROM posts WHERE username=? ORDER BY id DESC", (username,))
    posts = c.fetchall()

    # Fetch user status
    c.execute("SELECT status FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()

    user_status = row[0] if row else "✅ Safe"

    return render_template("profile.html", username=username, posts=posts, user_status=user_status)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
