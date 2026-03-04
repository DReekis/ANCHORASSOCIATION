
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
import cloudinary
import cloudinary.api
import razorpay

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Security Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-fallback-secret-key')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# CSRF
csrf = CSRFProtect(app)

#  CSP
csp = {
    'default-src': "'self'",
    'script-src': [
        "'self'",
        "'unsafe-inline'",
        'https://checkout.razorpay.com',
        'https://unpkg.com',
        'https://cdn.jsdelivr.net',
    ],
    'style-src': [
        "'self'",
        'https://fonts.googleapis.com',
        "'unsafe-inline'",
    ],
    'font-src': [
        "'self'",
        'https://fonts.gstatic.com',
    ],
    'img-src': [
        "'self'",
        'data:',
        'https://res.cloudinary.com',
        'https://images.unsplash.com',
        'https://grainy-gradients.vercel.app',
    ],
    'connect-src': [
        "'self'",
        'https://lumberjack.razorpay.com',
        'https://api.razorpay.com',
    ],
    'frame-src': [
        "'self'",
        'https://api.razorpay.com',
        'https://www.google.com',
    ],
}

Talisman(app, content_security_policy=csp, force_https=False)

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# Initialize Razorpay client
client = razorpay.Client(auth=(os.getenv('RZP_KEY_ID'), os.getenv('RZP_KEY_SECRET')))


@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}


@app.route('/')
def home():
    home_slides = []
    try:
        result = cloudinary.api.resources(
            type='upload',
            prefix='anchor/gallery/',
            max_results=10,
            resource_type='image'
        )
        for r in result.get('resources', []):
            home_slides.append({'url': r['secure_url']})
    except Exception:
        pass  # gracefully fall back to empty
    return render_template('index.html', home_slides=home_slides)


@app.route('/projects')
def projects():
    return render_template('projects.html')


@app.route('/gallery')
def gallery():
    categories = ['education', 'environment', 'community']
    images = []
    for cat in categories:
        try:
            result = cloudinary.api.resources(
                type='upload',
                prefix=f'anchor/gallery/{cat}/',
                max_results=30,
                resource_type='image'
            )
            for r in result.get('resources', []):
                images.append({
                    'url': r['secure_url'],
                    'category': cat,
                    'public_id': r['public_id']
                })
        except Exception:
            pass  # gracefully skip if folder doesn't exist yet
    return render_template('gallery.html', images=images)


@app.route('/donate')
def donate():
    return render_template('donate.html', rzp_key=os.getenv('RZP_KEY_ID'))


@app.route('/cafe')
def cafe():
    return render_template('cafe.html')


# --- Razorpay API ---


@app.route('/api/create_order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        amount = int(data.get('amount', 0))
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400

        order = client.order.create({
            'amount': amount * 100,
            'currency': 'INR',
            'payment_capture': '1'
        })
        return jsonify({
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify_payment', methods=['POST'])
def verify_payment():
    try:
        data = request.get_json()
        client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
        return jsonify({'status': 'success'})
    except razorpay.errors.SignatureVerificationError:
        return jsonify({'status': 'failure', 'error': 'Invalid payment signature'}), 400
    except Exception as e:
        return jsonify({'status': 'failure', 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False)
