import os
import re

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")


def to_email(username):
    return f"{username}@todo.local"


def save_tokens(sess):
    session["access_token"] = sess.access_token
    session["refresh_token"] = sess.refresh_token


def user_client():
    """Supabase client acting as the logged-in user, so RLS applies. None if not logged in."""
    if "access_token" not in session:
        return None
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        res = sb.auth.set_session(session["access_token"], session["refresh_token"])
        save_tokens(res.session)  # tokens may have been refreshed
    except Exception:
        session.clear()
        return None
    return sb


@app.route("/")
def index():
    sb = user_client()
    if not sb:
        return redirect(url_for("login"))
    profile = sb.table("profiles").select("profile_name").single().execute().data
    todos = sb.table("todos").select("id, text").order("created_at").execute().data
    return render_template("index.html", name=profile["profile_name"], todos=todos)


@app.post("/add")
def add():
    sb = user_client()
    if not sb:
        return redirect(url_for("login"))
    text = request.form["text"].strip()
    if text:
        sb.table("todos").insert({"text": text}).execute()
    return redirect(url_for("index"))


@app.post("/delete/<int:todo_id>")
def delete(todo_id):
    sb = user_client()
    if not sb:
        return redirect(url_for("login"))
    sb.table("todos").delete().eq("id", todo_id).execute()
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        profile_name = request.form["profile_name"].strip()
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        if not profile_name or not USERNAME_RE.match(username):
            flash("Username must be 3-30 letters, numbers or underscores, and profile name is required.")
            return render_template("register.html")
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            res = sb.auth.sign_up({
                "email": to_email(username),
                "password": password,
                "options": {"data": {"username": username, "profile_name": profile_name}},
            })
        except Exception as e:
            flash(f"Could not register: {e}")
            return render_template("register.html")
        if not res.session:
            flash("Registered, but no session returned. Turn off 'Confirm email' in Supabase.")
            return redirect(url_for("login"))
        save_tokens(res.session)
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            res = sb.auth.sign_in_with_password({"email": to_email(username), "password": request.form["password"]})
        except Exception:
            flash("Wrong username or password.")
            return render_template("login.html")
        save_tokens(res.session)
        return redirect(url_for("index"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
