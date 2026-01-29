import os
import cloudinary
import cloudinary.uploader
from flask_caching import Cache
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

from helpers import login_required
from db import get_db, get_cursor, close_db

# Load environment variables from .env file
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# Initialize Flask app
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

# Set secret key for sessions
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Configure cache
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configure session to use cachelib (instead of filesystem)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "cachelib"
app.config["SESSION_CACHELIB"] = cache
Session(app)

# Register database teardown
app.teardown_appcontext(close_db)

#########################################################################

# Helper Functions
def get_cloudinary_public_id(url):
    """Extract public_id from Cloudinary URL"""
    if not url:
        return None
    try:
        # URL format: https://res.cloudinary.com/cloud_name/image/upload/v123456/folder/filename.ext
        parts = url.split('/')
        # Get folder/filename without extension
        folder_file = '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        return folder_file.rsplit('.', 1)[0]
    except:
        return None

#########################################################################

# Routes
# Route for homepage
@app.route("/")
@cache.cached(timeout=60)
def home():
    cursor = get_cursor()
    cursor.execute("SELECT * FROM projects ORDER BY \"order\" ASC")
    projects = cursor.fetchall()
    
    return render_template("home.html", projects=projects)

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
            flash("Last name is required", "error")
            return redirect("/aboutme")
        if not email:
            flash("Email is required", "error")
            return redirect("/aboutme")
        if not message:
            flash("Message is required", "error")
            return redirect("/aboutme")

        cursor = get_cursor()
        cursor.execute(
            "INSERT INTO contact (fname, lname, email, message) VALUES (%s, %s, %s, %s)", 
            (fname, lname, email, message)
        )
        get_db().commit()
        flash("Message sent successfully!", "success")
        return redirect("/")
    else:
        return render_template("aboutme.html")

#########################################################################

# Dashboard Routes
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
            flash("Username is required", "error")
            return redirect("/login")
        
        # Redirect user to login if user didn't input a password        
        if not password:
            flash("Password is required", "error")
            return redirect("/login")
        
        # Get the user if exist
        cursor = get_cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        users = cursor.fetchall()

        # Check if user exists and password matches
        if len(users) != 1 or not check_password_hash(users[0]['password'], password):
            flash("Invalid username or password", "error")
            return redirect("/login")

        # Remember which user logged in 
        session["user_id"] = users[0]['id']
        return redirect("/dashboard")
    else:
        return render_template("dashboard/login.html")

# Route for dashboard (Login Required)
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        btn = request.form.get("btn")
        cursor = get_cursor()
        cursor.execute("SELECT * FROM projects WHERE id = %s", (btn,))
        record = cursor.fetchall()
        return render_template("/dashboard/update.html", record=record)
    else:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM projects ORDER BY \"order\" ASC")
        projects = cursor.fetchall()

        cursor.execute("SELECT * FROM contact")
        contacts = cursor.fetchall()

        return render_template("dashboard/records.html", project=projects, contact=contacts)

# Route for adduser (Login Required)
@app.route("/dashboard/adduser", methods=["GET", "POST"])
@login_required
def adduser():
    # If method is Post get the user input
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate inputs
        if not username:
            flash("Username is required", "error")
            return redirect("/dashboard/adduser")
        
        if not password:
            flash("Password is required", "error")
            return redirect("/dashboard/adduser")
        
        # Hash password and insert user
        hashed_password = generate_password_hash(password)
        cursor = get_cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)", 
                (username, hashed_password)
            )
            get_db().commit()
            flash("User added successfully!", "success")
        except Exception as e:
            flash(f"Error adding user: {str(e)}", "error")
            return redirect("/dashboard/adduser")
        
        return redirect("/dashboard")
    else: 
        return render_template("dashboard/adduser.html")

# Route for addproject (Login Required)
@app.route("/dashboard/addproject", methods=["GET", "POST"])
@login_required
def addproject():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        languages = request.form.get("languages")
        video_url = request.form.get("video") or None  # Convert empty string to None
        git_url = request.form.get("git_url") or None  # Convert empty string to None
        live_url = request.form.get("live_url") or None  # Convert empty string to None
        order = request.form.get("order")
        
        # Convert order to int or None
        try:
            order = int(order) if order and order.strip() else None
        except ValueError:
            flash("Order must be a valid integer", "error")
            return redirect("/dashboard/addproject")

        if not name:
            flash("Project name is required", "error")
            return redirect("/dashboard/addproject")
        
        if not description:
            flash("Description is required", "error")
            return redirect("/dashboard/addproject")
        
        if not languages:
            flash("Languages are required", "error")
            return redirect("/dashboard/addproject")
        
        # Validate order is unique
        if order:
            cursor = get_cursor()
            cursor.execute("SELECT id FROM projects WHERE \"order\" = %s", (order,))
            existing = cursor.fetchall()
            
            if existing:
                flash(f"Order {order} is already in use", "error")
                return redirect("/dashboard/addproject")
        
        # Upload image to Cloudinary
        image_url = None
        if 'img' in request.files:
            img = request.files["img"]
            if img and img.filename != '':
                try:
                    upload_result = cloudinary.uploader.upload(
                        img,
                        folder="portfolio/images",
                        resource_type="image"
                    )
                    image_url = upload_result['secure_url']
                except Exception as e:
                    flash(f"Image upload failed: {str(e)}", "error")
                    return redirect("/dashboard/addproject")

        # Save in database (video is just a URL string)
        cursor = get_cursor()
        cursor.execute(
            "INSERT INTO projects (name, description, languages, img, video, git_url, live_url, \"order\") VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
            (name, description, languages, image_url, video_url, git_url, live_url, order)
        )
        get_db().commit()
        flash("Project added successfully!", "success")

        return redirect("/dashboard")
    else:
        return render_template("dashboard/addproject.html")
    
# Route for Update Record (Login Required)
@app.route("/dashboard/update", methods=["GET", "POST"])
@login_required
def update():
    if request.method == "POST":
        project_id = request.form.get("id")
        name = request.form.get("name")
        description = request.form.get("description")
        languages = request.form.get("languages")
        video_url = request.form.get("video")  # YouTube URL from text input
        git_url = request.form.get("git_url")
        live_url = request.form.get("live_url")
        order = request.form.get("order")

        # Validate order is unique (excluding current project)
        if order:
            cursor = get_cursor()
            cursor.execute(
                "SELECT id FROM projects WHERE \"order\" = %s AND id != %s", 
                (order, project_id)
            )
            existing = cursor.fetchall()
            
            if existing:
                flash(f"Order {order} is already used by another project", "error")
                return redirect("/dashboard")

        cursor = get_cursor()
        cursor.execute("SELECT img FROM projects WHERE id = %s", (project_id,))
        result = cursor.fetchall()
        
        if not result:
            flash("Project not found", "error")
            return redirect("/dashboard")
            
        old_image_url = result[0]['img']
        
        if not name:
            flash("Project name is required", "error")
            return redirect("/dashboard")
        
        if not description:
            flash("Description is required", "error")
            return redirect("/dashboard")
        
        if not languages:
            flash("Languages are required", "error")
            return redirect("/dashboard")
        
        # Handle image upload/removal
        image_url = old_image_url
        if 'img' in request.files:
            img = request.files["img"]
            if img and img.filename != '':
                # Delete old image from Cloudinary
                if old_image_url:
                    try:
                        public_id = get_cloudinary_public_id(old_image_url)
                        if public_id:
                            cloudinary.uploader.destroy(public_id, resource_type="image")
                    except Exception as e:
                        print(f"Failed to delete old image: {e}")
                
                # Upload new image
                try:
                    upload_result = cloudinary.uploader.upload(
                        img,
                        folder="portfolio/images",
                        resource_type="image"
                    )
                    image_url = upload_result['secure_url']
                except Exception as e:
                    flash(f"Image upload failed: {str(e)}", "error")
                    return redirect("/dashboard")
        elif request.form.get("remove_img"):
            # Remove image
            if old_image_url:
                try:
                    public_id = get_cloudinary_public_id(old_image_url)
                    if public_id:
                        cloudinary.uploader.destroy(public_id, resource_type="image")
                except Exception as e:
                    print(f"Failed to delete image: {e}")
            image_url = None

        # Video is now just a URL, handle clearing if checkbox is checked
        if request.form.get("remove_video"):
            video_url = None

        # Save in database
        cursor.execute(
            "UPDATE projects SET name = %s, description = %s, languages = %s, img = %s, video = %s, git_url = %s, live_url = %s, \"order\" = %s WHERE id = %s", 
            (name, description, languages, image_url, video_url, git_url, live_url, order, project_id)
        )
        get_db().commit()
        flash("Project updated successfully!", "success")

        return redirect("/dashboard")
    else:    
        return redirect("/dashboard")

# Route for Delete Record (Login Required)
@app.route("/dashboard/delete", methods=["GET", "POST"])
@login_required
def delete():
    if request.method == "POST":
        record_id = request.form.get("btn")
        
        # Get project to delete associated image from Cloudinary
        cursor = get_cursor()
        cursor.execute("SELECT img FROM projects WHERE id = %s", (record_id,))
        result = cursor.fetchall()
        
        if result:
            img_url = result[0]['img']
            
            # Delete image from Cloudinary (video is just a URL, no deletion needed)
            if img_url:
                try:
                    public_id = get_cloudinary_public_id(img_url)
                    if public_id:
                        cloudinary.uploader.destroy(public_id, resource_type="image")
                except Exception as e:
                    print(f"Failed to delete image from Cloudinary: {e}")
        
        # Delete from database
        cursor.execute("DELETE FROM projects WHERE id = %s", (record_id,))
        get_db().commit()
        flash("Project deleted successfully!", "success")
        
        return redirect("/dashboard")
    else:
        return redirect("/dashboard")

# Route for Logout (Login Required)
@app.route("/dashboard/logout")
@login_required
def logout():
    # Forget any user_id
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)