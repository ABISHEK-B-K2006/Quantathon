import sqlite3
from sklearn.ensemble import GradientBoostingClassifier
import pandas as pd
import random
from datetime import datetime
import requests
import os

# ----- Config -----
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
GOOGLE_SAFE_BROWSING_API_KEY = "AIzaSyDLZ9NvtS3_yM14oLN75wPHpkn65tFhRas"
USE_SAFE_BROWSING = True
FRAUD_THRESHOLD = 2  # number of fraud posts before marking account Red

PHISHING_KEYWORDS = [
    'free','win','winner','verify','account','suspension','password','urgent','confirm',
    'secure','claim','prize','click','update','login','bank','ssn','transfer'
]
SHORTENER_DOMAINS = ['bit.ly','tinyurl.com','t.co','goo.gl','ow.ly','is.gd','buff.ly']

SAFE_BROWSING_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find?key={}"

# ----------------- Init tables -----------------
def init_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # posts + users already exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS detections(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            username TEXT,
            timestamp TEXT,
            ml_prob REAL,
            rules TEXT,
            unsafe_link INTEGER,
            final_status TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS url_cache(
            url TEXT PRIMARY KEY,
            safe INTEGER,
            checked_at TEXT
        )
    ''')
    # add fraud_count to users if missing
    try:
        c.execute("ALTER TABLE users ADD COLUMN fraud_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # already exists
    conn.commit()
    conn.close()

init_tables()

# ----------------- Safe Browsing with cache -----------------
def is_url_safe(url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT safe FROM url_cache WHERE url=?", (url,))
    row = c.fetchone()
    if row is not None:
        safe = bool(row[0])
        conn.close()
        return safe
    conn.close()

    if not USE_SAFE_BROWSING:
        return True

    try:
        endpoint = SAFE_BROWSING_ENDPOINT.format(GOOGLE_SAFE_BROWSING_API_KEY)
        payload = {
            "client": {"clientId": "FraudDashboard", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        resp = requests.post(endpoint, json=payload, timeout=6)
        safe = True
        if resp.status_code == 200:
            j = resp.json()
            if j.get("matches"):
                safe = False
        # cache result
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO url_cache(url, safe, checked_at) VALUES (?,?,?)",
                  (url, int(safe), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return safe
    except Exception:
        return True  # fail safe

# ----------------- ML model (synthetic training) -----------------
def generate_training_data(samples=1000):
    data = []
    for _ in range(samples):
        age = random.randint(0, 1000)
        ratio = random.random() * 2
        links = random.randint(0, 5)
        short = 1 if random.random() > 0.8 else 0
        urgency = random.randint(0, 5)
        fraud = 0
        if (age < 30 and short == 1 and urgency > 1) or (short == 1 and urgency > 3) or (age < 2 and links > 0):
            fraud = 1
        data.append([age, ratio, links, short, urgency, fraud])
    return pd.DataFrame(data, columns=['account_age_days','follower_ratio','num_links','uses_shortener','urgency_keywords','is_fraudulent'])

training_df = generate_training_data()
X = training_df.drop('is_fraudulent', axis=1)
y = training_df['is_fraudulent']
model = GradientBoostingClassifier(random_state=42)
model.fit(X, y)

# ----------------- Feature extraction -----------------
def extract_features(text):
    text_low = text.lower()
    urgency = sum(1 for word in PHISHING_KEYWORDS if word in text_low)
    short = 1 if any(domain in text_low for domain in SHORTENER_DOMAINS) else 0
    links = [w for w in text.split() if w.startswith("http") or w.startswith("www")]
    num_links = len(links)
    age = random.randint(0, 1000)
    ratio = random.random() * 2
    return [age, ratio, num_links, short, urgency]

# ----------------- Rule-based checks -----------------
def rule_based_flag(text):
    text_low = text.lower()
    reasons = []
    if any(word in text_low for word in PHISHING_KEYWORDS):
        reasons.append("keyword")
    if any(domain in text_low for domain in SHORTENER_DOMAINS):
        reasons.append("shortener")
    if sum(1 for w in text.split() if w.startswith("http")) > 2:
        reasons.append("many_links")
    if any(chunk.isupper() and len(chunk) > 4 for chunk in text.split()):
        reasons.append("all_caps")
    return (len(reasons) > 0), reasons

# ----------------- Detector -----------------
def run_detector(prob_threshold=0.70):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, text FROM posts WHERE status='Pending'")
    pending_posts = c.fetchall()

    for pid, username, text in pending_posts:
        features = extract_features(text)
        prob = model.predict_proba([features])[0][1]

        rule_flag, reasons = rule_based_flag(text)
        links = [w for w in text.split() if w.startswith("http") or w.startswith("www")]
        unsafe_link_found = any(not is_url_safe("http://" + l if l.startswith("www") else l) for l in links)

        fraud = False
        fraud_reasons = []
        if prob >= prob_threshold:
            fraud, fraud_reasons = True, fraud_reasons + [f"ml_prob={prob:.2f}"]
        if rule_flag:
            fraud, fraud_reasons = True, fraud_reasons + ["rules:" + ",".join(reasons)]
        if unsafe_link_found:
            fraud, fraud_reasons = True, fraud_reasons + ["unsafe_link"]

        status = "⚠️ Fraud Detected" if fraud else "✅ Safe"
        status_full = f"{status} ({';'.join(fraud_reasons) if fraud_reasons else 'no_reasons'})"

        # Update post
        c.execute("UPDATE posts SET status=? WHERE id=?", (status_full, pid))

        # Update detection log
        c.execute("""INSERT INTO detections(post_id, username, timestamp, ml_prob, rules, unsafe_link, final_status)
                     VALUES (?,?,?,?,?,?,?)""",
                  (pid, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   float(prob), ",".join(reasons), int(unsafe_link_found), status))

        # Update user account
        c.execute("SELECT fraud_count, status FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if fraud:
            if row is None:
                c.execute("INSERT INTO users(username, status, fraud_count) VALUES (?,?,?)",
                          (username, "🚨 Red" if FRAUD_THRESHOLD <= 1 else "✅ Safe", 1))
            else:
                fc, current_status = row
                fc = (fc or 0) + 1
                if fc >= FRAUD_THRESHOLD:
                    c.execute("UPDATE users SET status=?, fraud_count=? WHERE username=?",
                              ("🚨 Red", fc, username))
                else:
                    c.execute("UPDATE users SET fraud_count=? WHERE username=?", (fc, username))
        else:
            if row is None:
                c.execute("INSERT INTO users(username, status, fraud_count) VALUES (?,?,?,)",
                          (username, "✅ Safe", 0))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_detector()
    print("Detector run completed")
