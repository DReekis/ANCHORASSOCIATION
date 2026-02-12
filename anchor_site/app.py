
import os
from datetime import datetime
from flask import Flask, render_template
import cloudinary
import cloudinary.api

# Initialize Flask app
app = Flask(__name__)

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)


@app.context_processor
def inject_year():
    """Inject the current year into all templates for copyright."""
    return {'current_year': datetime.now().year}


@app.route('/')
def home():
    """Render the home page."""
    return render_template('index.html')


@app.route('/projects')
def projects():
    """Render the projects page."""
    return render_template('projects.html')


@app.route('/gallery')
def gallery():
    """Render the gallery page."""
    return render_template('gallery.html')


@app.route('/resort')
def resort():
    """Render the resort page."""
    return render_template('resort.html')


@app.route('/donate')
def donate():
    """Render the donate page."""
    return render_template('donate.html')


if __name__ == '__main__':
    app.run(debug=True)


