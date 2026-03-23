
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
import cloudinary
import cloudinary.api
import razorpay

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

app = Flask(__name__, static_folder=None)

@app.route('/static/<path:filename>', endpoint='static')
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)

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


# Cloudinary Configuration
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
rzp_key_id = os.getenv('RZP_KEY_ID')
rzp_key_secret = os.getenv('RZP_KEY_SECRET')

client = None
if rzp_key_id and rzp_key_secret:
    client = razorpay.Client(auth=(rzp_key_id, rzp_key_secret))
else:
    app.logger.warning(
        'Razorpay is not fully configured. Set RZP_KEY_ID and RZP_KEY_SECRET to enable payments.'
    )


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
    if normalized_folder.startswith('Home/'):
        normalized_folder = normalized_folder[5:]
    if not normalized_folder:
        return []

    images = []
    try:
        if hasattr(cloudinary.api, 'resources_by_asset_folder'):
            result = cloudinary.api.resources_by_asset_folder(
                asset_folder=normalized_folder,
                max_results=max_results
            )
            for resource in result.get('resources', []):
                secure_url = resource.get('secure_url')
                if secure_url:
                    images.append({'url': secure_url})
            if images:
                return images
    except Exception as e:
        pass

    try:
        result = cloudinary.api.resources(
            type='upload',
            prefix=f'{normalized_folder}/',
            max_results=max_results,
            resource_type='image'
        )
        for resource in result.get('resources', []):
            secure_url = resource.get('secure_url')
            if secure_url:
                images.append({'url': secure_url})
    except Exception as e:
        app.logger.warning('Failed to load Cloudinary folder "%s": %s', normalized_folder, e)

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
    folder_path = 'anchor/gallery'
    images = []
    try:
        result = {}
        if hasattr(cloudinary.api, 'resources_by_asset_folder'):
            try:
                result = cloudinary.api.resources_by_asset_folder(
                    asset_folder=folder_path,
                    max_results=100
                )
            except Exception:
                pass
        
        if not result or not result.get('resources'):
            result = cloudinary.api.resources(
                type='upload',
                prefix=f'{folder_path}/',
                max_results=100,
                resource_type='image'
            ) or {}

        for r in result.get('resources', []):
            images.append({
                'url': r['secure_url'],
                'public_id': r['public_id']
            })
    except Exception as e:
        app.logger.warning('Failed to load Cloudinary gallery: %s', e)

    import random
    random.shuffle(images)

    return render_template('gallery.html', images=images)


@app.route('/donate')
def donate():
    return render_template('donate.html', rzp_key=rzp_key_id)


@app.route('/cafe')
def cafe():
    return render_template('cafe.html')


# --- Razorpay API ---


@app.route('/api/create_order', methods=['POST'])
def create_order():
    if client is None:
        return jsonify({'error': 'Payment gateway is not configured'}), 503

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
    if client is None:
        return jsonify({'status': 'failure', 'error': 'Payment gateway is not configured'}), 503

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
