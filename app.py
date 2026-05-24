from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change_this_secret_key"
DATABASE = "database.db"


def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def setup():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT,
        last_name TEXT,
        username TEXT UNIQUE,
        email TEXT,
        password TEXT,
        gender TEXT,
        dob TEXT,
        verified INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user',
        has_voted INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        logo TEXT,
        votes INTEGER DEFAULT 0
    )
    """)

    c.execute("SELECT * FROM users WHERE role='admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users(first_name,last_name,username,email,password,role,verified) VALUES(?,?,?,?,?,?,?)",
            ("Admin", "User", "admin", "admin@vote.com", generate_password_hash("@771772#"), "admin", 1),
        )

    c.execute("SELECT * FROM candidates")
    if not c.fetchone():
        c.executemany(
            "INSERT INTO candidates(name, logo) VALUES(?, ?)",
            [
                ("BJP", "bjp.png"),
                ("Congress", "congress.png"),
                ("AAP", "aap.png"),
            ],
        )

    conn.commit()
    conn.close()


setup()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Password and Confirm Password do not match!", "danger")
            return redirect("/register")

        conn = db()
        try:
            conn.execute(
                "INSERT INTO users(first_name,last_name,username,email,password) VALUES(?,?,?,?,?)",
                (first_name, last_name, username, email, generate_password_hash(password)),
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Username already exists!", "danger")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["name"] = ((user["first_name"] or "") + " " + (user["last_name"] or "")).strip()
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect("/admin")
            return redirect("/profile")

        flash("Invalid username or password!", "danger")

    return render_template("login.html")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session or session.get("role") != "user":
        return redirect("/login")

    conn = db()
    if request.method == "POST":
        gender = request.form.get("gender")
        dob = request.form.get("dob")
        conn.execute("UPDATE users SET gender=?, dob=?, verified=1 WHERE id=?", (gender, dob, session["user_id"]))
        conn.commit()
        flash("Verification completed. Now you can vote.", "success")

    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("profile.html", user=user)


@app.route("/vote", methods=["GET", "POST"])
def vote():
    if "user_id" not in session or session.get("role") != "user":
        return redirect("/login")

    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

    if not user["verified"]:
        conn.close()
        flash("Please verify your profile first.", "warning")
        return redirect("/profile")

    if user["has_voted"]:
        conn.close()
        flash("You have already voted!", "info")
        return redirect("/results")

    candidates = conn.execute("SELECT * FROM candidates").fetchall()

    if request.method == "POST":
        candidate_id = request.form.get("candidate")
        conn.execute("UPDATE candidates SET votes = votes + 1 WHERE id=?", (candidate_id,))
        conn.execute("UPDATE users SET has_voted=1 WHERE id=?", (session["user_id"],))
        conn.commit()
        conn.close()
        flash("Vote submitted successfully!", "success")
        return redirect("/results")

    conn.close()
    return render_template("vote.html", candidates=candidates)


@app.route("/results")
def results():
    conn = db()
    candidates = conn.execute("SELECT * FROM candidates").fetchall()
    conn.close()
    return render_template("results.html", candidates=candidates)


@app.route("/admin")
def admin():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")
    conn = db()
    users = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    candidates = conn.execute("SELECT * FROM candidates").fetchall()
    conn.close()
    return render_template("admin_dashboard.html", users=users, candidates=candidates)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
