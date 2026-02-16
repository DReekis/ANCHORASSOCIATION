
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify
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
    return {'current_year': datetime.now().year}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/projects')
def projects():
    return render_template('projects.html')


@app.route('/gallery')
def gallery():
    return render_template('gallery.html')



@app.route('/donate')
def donate():
    return render_template('donate.html')


@app.route('/cafe')
def cafe():
    return render_template('cafe.html')


# --- Razorpay Mock API ---

@app.route('/api/create_order', methods=['POST'])
def create_order():
    data = request.get_json()
    amount = data.get('amount', 0)
    order_id = 'order_' + uuid.uuid4().hex[:16]
    return jsonify({
        'order_id': order_id,
        'amount': amount * 100,
        'currency': 'INR'
    })


@app.route('/api/verify_payment', methods=['POST'])
def verify_payment():
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run(debug=True)
