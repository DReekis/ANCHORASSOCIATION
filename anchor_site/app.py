
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
import cloudinary
import cloudinary.api
import razorpay

# Load environment variables from anchor_site/.env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

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

# Configure Cloudinary from environment variables.
# Supports either explicit keys or CLOUDINARY_URL.
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
cloud_api_key = os.environ.get('CLOUDINARY_API_KEY')
cloud_api_secret = os.environ.get('CLOUDINARY_API_SECRET')

if cloud_name and cloud_api_key and cloud_api_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloud_api_key,
        api_secret=cloud_api_secret
    )
elif os.environ.get('CLOUDINARY_URL'):
    cloudinary.config()
else:
    app.logger.warning(
        'Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME/CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET '
        'or CLOUDINARY_URL in anchor_site/.env'
    )

# Initialize Razorpay client
client = razorpay.Client(auth=(os.getenv('RZP_KEY_ID'), os.getenv('RZP_KEY_SECRET')))


def _parse_positive_int(raw_value, default_value):
    try:
        parsed = int(raw_value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return default_value


LIVE_GALLERY_FOLDER = os.getenv('CLOUDINARY_LIVE_GALLERY_FOLDER', 'anchor/live-gallery')
LIVE_GALLERY_LIMIT = _parse_positive_int(os.getenv('CLOUDINARY_LIVE_GALLERY_LIMIT'), 12)


def get_cloudinary_folder_images(folder_path, max_results=12):
    normalized_folder = (folder_path or '').strip().strip('/')
    if not normalized_folder:
        return []

    result = cloudinary.api.resources(
        type='upload',
        prefix=f'{normalized_folder}/',
        max_results=max_results,
        direction='desc',
        resource_type='image'
    )

    images = []
    for resource in result.get('resources', []):
        secure_url = resource.get('secure_url')
        if secure_url:
            images.append({'url': secure_url})
    return images


@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}


@app.route('/')
def home():
    home_slides = []
    try:
        home_slides = get_cloudinary_folder_images(
            folder_path=LIVE_GALLERY_FOLDER,
            max_results=LIVE_GALLERY_LIMIT
        )
    except Exception as e:
        app.logger.warning('Failed to load home live-gallery images from Cloudinary: %s', e)
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
        except Exception as e:
            app.logger.warning('Failed to load Cloudinary gallery category "%s": %s', cat, e)
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
