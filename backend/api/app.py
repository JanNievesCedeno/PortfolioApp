import os
import sqlite3
from flask_caching import Cache
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Database connection
database = sqlite3.connect("portfolio.db", check_same_thread=False)

# Database cursor
db = database.cursor()

#########################################################################

# Routes
# Route for homepage
@app.route("/")
@cache.cached(timeout=60)
def home():
    user_id = 7
    db.execute("SELECT name, description, languages, img, video FROM projects WHERE user_id = ?", (user_id,))
    projects = db.fetchall()

    return render_template("home.html", projects=projects)

# Route for resume
# @app.route("/resume")
# def projects():
#     return render_template("resume.html")

# Route for aboutme
@app.route("/aboutme", methods=["GET", "POST"])
def aboutme():
    if request.method == "POST":
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        email = request.form.get("email")
        message = request.form.get("message")

        if not fname:
            flash("First name is required", "error")
            return redirect("/aboutme")
        if not lname:
            return redirect("/aboutme")
        if not email:
            return redirect("/aboutme")
        if not message:
            return redirect("/aboutme")

        db.execute("INSERT INTO contact (fname, lname, email, message) VALUES (?, ?, ?, ?)", (fname, lname, email, message,))
        database.commit()
        return redirect("/")
    else:
        return render_template("aboutme.html")

#########################################################################

# Dashboad Routes
# Route for login 
@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget any user_id
    session.clear()

    # If method is Post get the user input
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Redirect user to login if user didn't input a username
        if not username:
            return redirect("/login")
        
        # Redirect user to login if user didn't input a password        
        if not password:
            return redirect("/login")
        
        # Get the user if exist
        db.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = db.fetchall()
        print(user)

        # If password doesn't match redirect the user back to login
        if len(user) != 1 or not check_password_hash(user[0][2], password):
            return redirect("/login")
        
        # Remember which user logged in 
        session["user_id"] = user[0][0]
        
        return redirect("/dashboard")
    else:
        return render_template("dashboard/login.html")

# Route for dashboard (Login Required)
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():

    if request.method == "POST":
        btn = request.form.get("btn")
        record = db.execute("SELECT * FROM projects WHERE id = ?", (btn,))
        record = db.fetchall()
        return render_template("/dashboard/update.html", record=record)

    else:
        user_id = session.get("user_id")
        db.execute("SELECT id, name, description, languages, img, video  FROM projects WHERE user_id = ?", (user_id,))
        project = db.fetchall()

        db.execute("SELECT * FROM contact")
        contact = db.fetchall()

        return render_template("dashboard/records.html", project=project, contact=contact)

# Route for adduser (Login Required)
@app.route("/dashboard/adduser", methods=["GET", "POST"])
@login_required
def adduser():

    # If method is Post get the user input
    if request.method == "POST":
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        # Redirect user to login if user didn't input a username
        if not username:
            return redirect("/dashboard/adduser")
        
        # Redirect user to login if user didn't input a password        
        if not password:
            return redirect("/dashboard/adduser")
        
        # Get the user if exist
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password,))
        database.commit()
        
        return redirect("/dashboard")
    else: 
        return render_template("dashboard/adduser.html")

# Route for addproject (Login Required)
@app.route("/dashboard/addproject", methods=["GET", "POST"])
@login_required
def addproject():

    if request.method == "POST":
        user_id = session.get("user_id")
        name = request.form.get("name")
        description = request.form.get("description")
        languages = request.form.get("languages")
        img = None
        video = None

        if not name:
            return redirect("/dashboard/addproject")
        
        # Redirect user to addproject if user didn't input a description
        if not description:
            return redirect("/dashboard/addproject")
        
        # Redirect user to addproject if user didn't input a languages
        if not languages:
            return redirect("/dashboard/addproject")
        
        # Request files for the image
        if 'img' in request.files:
            img = request.files["img"]
            if not img.filename == '':
                image_path = os.path.join("static/img", img.filename)
                img.save(image_path)
        
            else:
                image_path = None

        # Request files for the video
        if 'video' in request.files:
            video = request.files["video"]
            if not video.filename == '':
                video_path = os.path.join("static/video", video.filename)
                video.save(video_path)       
        
            else:
                video_path = None

        # Save in database
        db.execute("INSERT INTO projects (name, description, languages, img, video, user_id) VALUES (?, ?, ?, ?, ?, ?)", (name, description, languages, image_path, video_path, user_id,))
        database.commit()
        
        # if img:
        #     os.remove(image_path)
        # if video:
        #     os.remove(video_path)

        return redirect("/dashboard")
    else:
        return render_template("dashboard/addproject.html")
    
# Route for Update Record (Login Required)
@app.route("/dashboard/update", methods=["GET", "POST"])
@login_required
def update():

    if request.method == "POST":
        print(request.form)
        id = request.form.get("id")
        name = request.form.get("name")
        description = request.form.get("description")
        languages = request.form.get("languages")
        img = None
        video = None

        db.execute("SELECT img, video FROM projects WHERE id = ?", (id,))
        path = db.fetchall()        
        image_path = path[0][0]
        video_path = path[0][1]
        
        if not name:
            return redirect("/dashboard/update")
        
        # Redirect user to update if user didn't input a description
        if not description:
            return redirect("/dashboard/update")
        
        # Redirect user to update if user didn't input a languages
        if not languages:
            return redirect("/dashboard/update")
        
        # Request files for the image
        if 'img' in request.files:
            img = request.files["img"]
            if not img.filename == '':
                if image_path:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                image_path = os.path.join("static/img", img.filename)
                img.save(image_path)
        
            else:
                if os.path.exists(image_path):
                        os.remove(image_path)
                image_path = None

        # Request files for the video
        if 'video' in request.files:
            video = request.files["video"]
            if not video.filename == '':
                if video_path:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                video_path = os.path.join("static/video", video.filename)
                video.save(video_path)       
        
            else:
                if video_path:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                video_path = None

        # Save in database
        db.execute("UPDATE projects SET name = ?, description = ?, languages = ?, img = ?, video = ? WHERE id = ?", (name, description, languages, image_path, video_path, id,))
        database.commit()

        return redirect("/dashboard")
    else:    
        return redirect ("/dashboard")

# Route for Delete Record (Login Required)
@app.route("/dashboard/delete", methods=["GET", "POST"])
@login_required
def delete():
    print(request.form)
    if request.method == "POST":
        record = request.form.get("btn")
        print(record)
        db.execute("DELETE FROM projects WHERE id = ?", (record,))
        database.commit()
        return redirect ("/dashboard")
    else:
        return redirect("/dashboard")

# Route for Logout (Login Required)
@app.route("/dashboard/logout")
@login_required
def logout():

    # Forget any user_id
    session.clear()

    return redirect("/login")