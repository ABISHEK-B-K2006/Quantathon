import streamlit as st
import pandas as pd
import sqlite3
import os
import time
from detector import run_detector

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

st.set_page_config(page_title="Fraud Dashboard", layout="wide")
st.title("🚨 Real-Time Fraud Dashboard")

# Run detector once per refresh
run_detector()

# Fetch posts and users
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM posts ORDER BY id DESC LIMIT 50", conn)
users_df = pd.read_sql("SELECT * FROM users ORDER BY username", conn)
conn.close()

# Counters
col1, col2, col3 = st.columns(3)
total_posts = len(df)
total_safe = df['status'].str.contains("Safe").sum()
total_fraud = df['status'].str.contains("Fraud|⚠️").sum()

col1.metric("Total posts (shown)", total_posts)
col2.metric("Total Safe", int(total_safe))
col3.metric("Total Fraud Alerts", int(total_fraud))

# Styling helpers
def highlight_post(row):
    s = row["status"]
    if "Fraud" in s or "⚠️" in s or "unsafe_link" in s:
        return ["background-color:black"] * len(row)
    if "Safe" in s or "✅" in s:
        return ["background-color:black"] * len(row)
    return [""] * len(row)

def highlight_user(row):
    s = row["status"]
    if "Red" in s or "🚨" in s:
        return ["background-color:#FF6347"] * len(row)
    if "Safe" in s or "✅" in s:
        return ["background-color:#90EE90"] * len(row)
    return [""] * len(row)

# Show recent posts
st.subheader("📌 Recent Posts")
if not df.empty:
    display_df = df[['id','username','text','timestamp','status']].copy()
    st.dataframe(display_df.style.apply(highlight_post, axis=1), height=400)
else:
    st.write("No posts yet.")

# Show users
st.subheader("👥 Users / Account Status")
if not users_df.empty:
    st.dataframe(users_df.style.apply(highlight_user, axis=1), height=300)
else:
    st.write("No users yet.")

# Simple filter / inspect
st.subheader("🔎 Inspect a user's posts")
if not users_df.empty:
    user_choice = st.selectbox("Select user", options=["(all)"] + users_df['username'].tolist())
    if user_choice and user_choice != "(all)":
        conn = sqlite3.connect(DB_PATH)
        user_posts = pd.read_sql("SELECT * FROM posts WHERE username=? ORDER BY id DESC LIMIT 50", conn, params=(user_choice,))
        conn.close()
        st.write(f"Showing recent posts for **{user_choice}**")
        if not user_posts.empty:
            st.dataframe(user_posts[['id','text','timestamp','status']].style.apply(highlight_post, axis=1), height=300)
        else:
            st.write("No posts for this user.")

st.markdown("---")
st.caption("Detector logic: hybrid ML + rule-based + Google Safe Browsing (if API key set).")

# --- Auto-refresh every 2 seconds ---
time.sleep(2)
st.rerun()
