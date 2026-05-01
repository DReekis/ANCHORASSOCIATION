
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlsplit, urlunsplit
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
import cloudinary
import cloudinary.api
import razorpay

try:
    from .models import db, AdminUser, InitiativeSection, InitiativeSubitem, HeroSlide, MemberStory
    from .admin_panel import setup_admin
except ImportError:
    from models import db, AdminUser, InitiativeSection, InitiativeSubitem, HeroSlide, MemberStory
    from admin_panel import setup_admin

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
PACKAGE_STATIC_DIR = os.path.join(BASE_DIR, 'static')
STATIC_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.avif', '.svg'}
load_dotenv(os.path.join(BASE_DIR, '.env'))
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=None)

@app.route('/static/<path:filename>', endpoint='static')
def static_files(filename):
    return send_from_directory(PACKAGE_STATIC_DIR, filename)


def find_static_image_by_terms(*terms):
    search_roots = (
        Path(PACKAGE_STATIC_DIR) / 'photos',
        Path(PACKAGE_STATIC_DIR) / 'images',
        Path(PACKAGE_STATIC_DIR),
    )
    normalized_terms = tuple(term.lower() for term in terms if term)

    for root in search_roots:
        if not root.exists():
            continue

        matches = []
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in STATIC_IMAGE_EXTENSIONS:
                continue

            stem = path.stem.lower()
            if all(term in stem for term in normalized_terms):
                relative_path = path.relative_to(PACKAGE_STATIC_DIR).as_posix()
                matches.append((len(relative_path), relative_path))

        if matches:
            matches.sort()
            return matches[0][1]

    return None

# Security Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-fallback-secret-key')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Database Config
db_url = os.environ.get('POSTGRES_URL', os.environ.get('DATABASE_URL'))
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or ('sqlite:///' + os.path.join(BASE_DIR, 'anchor.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# CSRF
csrf = CSRFProtect(app)

# Initialize Database & Admin
db.init_app(app)
setup_admin(app, db)

#  CSP
csp = {
    'default-src': "'self'",
    'script-src': [
        "'self'",
        "'unsafe-inline'",
        'https://checkout.razorpay.com',
        'https://unpkg.com',
        'https://cdn.jsdelivr.net',
        'https://cdnjs.cloudflare.com',
        'https://stackpath.bootstrapcdn.com',
        'https://code.jquery.com',
    ],
    'style-src': [
        "'self'",
        'https://fonts.googleapis.com',
        "'unsafe-inline'",
        'https://stackpath.bootstrapcdn.com',
        'https://cdnjs.cloudflare.com',
    ],
    'font-src': [
        "'self'",
        'https://fonts.gstatic.com',
        'https://cdnjs.cloudflare.com',
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
HERO_SLIDE_SRCSET_WIDTHS = (640, 960, 1280, 1600, 1920)
_CLOUDINARY_TRANSFORM_MARKER = '/upload/'
_HERO_OBJECT_POSITION_PATTERN = re.compile(
    r'^\s*(?:'
    r'(?:left|center|right|\d{1,3}(?:\.\d+)?%)'
    r'(?:\s+(?:top|center|bottom|\d{1,3}(?:\.\d+)?%))?'
    r'|'
    r'(?:top|center|bottom)(?:\s+(?:left|center|right|\d{1,3}(?:\.\d+)?%))?'
    r')\s*$',
    re.IGNORECASE,
)


def should_bootstrap_database():
    force_bootstrap = os.getenv('ANCHOR_BOOTSTRAP_DB', '').strip().lower() in {'1', 'true', 'yes'}
    is_vercel_runtime = bool(os.getenv('VERCEL') or os.getenv('VERCEL_ENV'))
    return force_bootstrap or not is_vercel_runtime


def _donation_link(purpose):
    return f"/donate?purpose={quote_plus(purpose)}"


def _is_cloudinary_image_url(image_url):
    if not image_url:
        return False

    parsed = urlsplit(str(image_url))
    return parsed.netloc.endswith('res.cloudinary.com') and _CLOUDINARY_TRANSFORM_MARKER in parsed.path


def _cloudinary_responsive_url(image_url, width):
    if not _is_cloudinary_image_url(image_url):
        return image_url

    parsed = urlsplit(str(image_url))
    path_prefix, path_suffix = parsed.path.split(_CLOUDINARY_TRANSFORM_MARKER, 1)
    first_segment, _, remainder = path_suffix.partition('/')
    transform = f'c_limit,w_{int(width)},q_auto,f_auto,dpr_auto,fl_progressive'

    if first_segment.startswith('v') and first_segment[1:].isdigit():
        new_path = f'{path_prefix}{_CLOUDINARY_TRANSFORM_MARKER}{transform}/{path_suffix}'
    elif remainder:
        new_path = f'{path_prefix}{_CLOUDINARY_TRANSFORM_MARKER}{first_segment},{transform}/{remainder}'
    else:
        new_path = f'{path_prefix}{_CLOUDINARY_TRANSFORM_MARKER}{transform}/{path_suffix}'

    return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))


def _build_cloudinary_srcset(image_url, widths):
    if not _is_cloudinary_image_url(image_url):
        return ''

    return ', '.join(
        f'{_cloudinary_responsive_url(image_url, width)} {int(width)}w'
        for width in widths
    )


def _normalize_percent(value, fallback=50.0):
    try:
        return max(0.0, min(float(value), 100.0))
    except (TypeError, ValueError):
        return fallback


def _normalize_object_position(raw_value):
    value = ' '.join(str(raw_value or '').strip().split())
    if not value or not _HERO_OBJECT_POSITION_PATTERN.fullmatch(value):
        return '50% 50%'

    normalized_tokens = []
    for token in value.split():
        lowered = token.lower()
        if lowered in {'left', 'center', 'right', 'top', 'bottom'}:
            normalized_tokens.append(lowered)
        else:
            normalized_tokens.append(f'{_normalize_percent(token.rstrip("%")):g}%')

    if len(normalized_tokens) == 1:
        if normalized_tokens[0] in {'top', 'center', 'bottom'}:
            normalized_tokens.insert(0, '50%')
        else:
            normalized_tokens.append('50%')

    return ' '.join(normalized_tokens[:2])


def _hero_slide_object_position(slide):
    explicit_position = (
        getattr(slide, 'object_position', None)
        or getattr(slide, 'focal_position', None)
    )
    if explicit_position:
        return _normalize_object_position(explicit_position)

    focal_x = getattr(slide, 'focal_x', None)
    focal_y = getattr(slide, 'focal_y', None)
    if focal_x is None and focal_y is None:
        return '50% 50%'

    return f'{_normalize_percent(focal_x):g}% {_normalize_percent(focal_y):g}%'


def _serialize_hero_slide(slide):
    title = (slide.title or '').strip()
    subtitle = (slide.subtitle or '').strip()

    return {
        'title': title,
        'subtitle': subtitle,
        'image_url': _cloudinary_responsive_url(slide.image_url, 1600),
        'image_srcset': _build_cloudinary_srcset(slide.image_url, HERO_SLIDE_SRCSET_WIDTHS),
        'image_sizes': '100vw',
        'alt_text': title or 'Anchor Association featured slide',
        'object_position': _hero_slide_object_position(slide),
    }


IMPACT_PAGE_SECTIONS = [
    {
        'id': 'impacts-over-the-years',
        'eyebrow': '01',
        'title': 'Impacts Over the Years',
        'copy': (
            'Anchor Association keeps building long-term community strength through '
            'education, eco-conscious livelihoods, healthcare, and guided learning support.'
        ),
    },
    {
        'id': 'success-stories',
        'eyebrow': '02',
        'title': 'Success & Stories',
        'copy': (
            'Each initiative is designed to create visible progress, from stronger schooling '
            'pathways to greater confidence, employability, and community participation.'
        ),
    },
    {
        'id': 'awards-recognition',
        'eyebrow': '03',
        'title': 'Awards & Recognition',
        'copy': (
            'This space is ready for institutional recognitions, media mentions, community '
            'appreciation, and milestone acknowledgements as the organization grows.'
        ),
    },
    {
        'id': 'areas-communities',
        'eyebrow': '04',
        'title': 'Areas & Communities',
        'copy': (
            'Our work is rooted in place: local learners, women-led groups, families, and '
            'neighborhood communities who benefit from consistent, practical support.'
        ),
    },
]

JOIN_MEMBER_HIGHLIGHTS = [
    {
        'eyebrow': 'Membership',
        'title': 'Become part of the working community.',
        'copy': (
            'Join as a member to contribute your time, perspective, and commitment to the '
            'organization’s long-term social work.'
        ),
    },
    {
        'eyebrow': 'Contribution',
        'title': 'Support programs beyond one-time moments.',
        'copy': (
            'Members help strengthen continuity across education, healthcare, awareness work, '
            'eco projects, and future local partnerships.'
        ),
    },
    {
        'eyebrow': 'Next Step',
        'title': 'Membership information can be finalized by the Anchor team.',
        'copy': (
            'This page is ready for your exact eligibility, fee, and application workflow once '
            'those details are confirmed.'
        ),
    },
]

DEFAULT_INITIATIVES = [
    {
        'slug': 'anchor-public-school',
        'title': 'Anchor Public School',
        'summary': 'Holistic education that grows confidence, discipline, and curiosity.',
        'description': (
            'Anchor Public School is designed to give learners a stable, joyful, and '
            'future-facing academic environment. The focus stays on strong foundational '
            'learning, individual care, and a culture where children can grow with dignity, '
            'creativity, and consistent encouragement.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Anchor Public School'),
        'media_url': 'https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Students learning in a classroom',
        'theme': 'forest',
        'display_style': 'feature',
        'order': 1,
        'subitems': [],
    },
    {
        'slug': 'eco-urban-hub',
        'title': 'Eco Urban Hub',
        'summary': 'Sustainability, hospitality, and local livelihood in one living project.',
        'description': (
            'Eco Urban Hub brings together environmental awareness, community gathering, and '
            'responsible enterprise. It is a space where sustainable design and everyday human '
            'connection meet, creating a public-facing initiative that can support both '
            'livelihood and local visibility.'
        ),
        'impact_label': 'Served Daily',
        'impact_value': '1,000+',
        'cta_label': 'Book Us',
        'cta_url': '/cafe',
        'media_url': '/static/photos/front_cafe.png',
        'media_alt': 'Bagan Bilash eco cafe exterior',
        'theme': 'clay',
        'display_style': 'feature',
        'order': 2,
        'subitems': ['Bagan Bilash'],
    },
    {
        'slug': 'self-help-group',
        'title': 'Self Help Group',
        'summary': 'Women-led self-reliance through shared learning and economic confidence.',
        'description': (
            'The self help group initiative creates practical support systems where women can '
            'build confidence, organize collectively, and strengthen income pathways through '
            'group-based participation and mentorship.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Nivedita SHG'),
        'media_url': 'https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Women gathered in a community learning session',
        'theme': 'sage',
        'display_style': 'feature',
        'order': 3,
        'subitems': ['Nivedita SHG'],
    },
    {
        'slug': 'children-activity-centre',
        'title': 'Children Activity Centre',
        'summary': 'A playful, caring space where children stay active and engaged.',
        'description': (
            'This initiative supports children through structured activities, guided play, '
            'creative engagement, and spaces that make learning feel safe and enjoyable. It is '
            'meant to keep childhood energetic, expressive, and socially connected.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Minions Fun House'),
        'media_url': 'https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Children participating in a joyful activity',
        'theme': 'sunrise',
        'display_style': 'feature',
        'order': 4,
        'subitems': ['Minions Fun House'],
    },
    {
        'slug': 'charitable-clinic',
        'title': 'Charitable Clinic',
        'summary': 'Accessible care for families who need dependable health support.',
        'description': (
            'The charitable clinic initiative focuses on reaching people with basic care, '
            'timely guidance, and a more compassionate healthcare experience. It supports the '
            'larger goal of reducing everyday vulnerability through regular community attention.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Finding Cures'),
        'media_url': 'https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Medical support consultation',
        'theme': 'ink',
        'display_style': 'feature',
        'order': 5,
        'subitems': ['Finding Cures'],
    },
    {
        'slug': 'language-learning-programme',
        'title': 'Language Learning Programme',
        'summary': 'Communication skills that open confidence, connection, and opportunity.',
        'description': (
            'Language learning becomes a bridge to wider participation. This programme helps '
            'learners express themselves with greater confidence and prepares them for stronger '
            'engagement in education, work, and public life.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Atma Katha'),
        'media_url': 'https://images.unsplash.com/photo-1455390582262-044cdead277a?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Language learning and reading materials',
        'theme': 'forest',
        'display_style': 'feature',
        'order': 6,
        'subitems': ['Atma Katha'],
    },
    {
        'slug': 'self-independent-learning',
        'title': 'Self Independent Learning',
        'summary': 'Learning support that builds initiative, focus, and self-belief.',
        'description': (
            'Self Independent Learning is shaped to encourage ownership in the learning process. '
            'It supports learners who need reinforcement, direction, and practical encouragement '
            'to continue growing with confidence.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Learn & Shine'),
        'media_url': 'https://images.unsplash.com/photo-1513258496099-48168024aec0?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Students learning independently together',
        'theme': 'clay',
        'display_style': 'feature',
        'order': 7,
        'subitems': ['Learn & Shine'],
    },
    {
        'slug': 'career-development-programme',
        'title': 'Career Development Programme',
        'summary': 'Career guidance that helps participants prepare for real opportunities.',
        'description': (
            'Career Development Programme is about readiness: clarity, presentation, and '
            'direction. It supports participants as they move from aspiration toward practical '
            'steps, stronger employability, and longer-term economic confidence.'
        ),
        'impact_label': 'Beneficiaries',
        'impact_value': '1,000+',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Career Edge'),
        'media_url': 'https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=1200&q=80',
        'media_alt': 'Young professionals in a collaborative workshop',
        'theme': 'sage',
        'display_style': 'feature',
        'order': 8,
        'subitems': ['Career Edge'],
    },
    {
        'slug': 'other-regular-activities',
        'title': 'Other Regular Activities',
        'summary': 'Consistent community action that keeps everyday support visible.',
        'description': (
            'These regular activities keep Anchor closely connected to community needs '
            'throughout the year.'
        ),
        'impact_label': 'Activities',
        'impact_value': '05',
        'cta_label': 'Support Us',
        'cta_url': _donation_link('Other Regular Activities'),
        'media_url': '',
        'media_alt': '',
        'theme': 'sunrise',
        'display_style': 'list',
        'order': 9,
        'subitems': [
            'Plantation',
            'Awareness (Women & Child)',
            'Blood Donation Camp',
            'Blanket Distribution in Winter',
            'Cloth Distribution during festive season',
        ],
    },
    {
        'slug': 'past-initiatives',
        'title': 'Past Initiatives',
        'summary': 'A record of responsive work delivered across urgent and special contexts.',
        'description': (
            'Past initiatives capture the breadth of Anchor’s response during specific community '
            'needs and milestone programs.'
        ),
        'impact_label': 'Archives',
        'impact_value': '05',
        'cta_label': 'Explore Impact',
        'cta_url': '/impacts#success-stories',
        'media_url': '',
        'media_alt': '',
        'theme': 'ink',
        'display_style': 'list',
        'order': 10,
        'subitems': [
            'Covid Awareness Programme',
            'Medical Camp',
            "'YAAS' Disaster Relief Programme",
            'Multi Talent Development Competition',
            'Orphan Feeding & Initiatives',
        ],
    },
]


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


def seed_default_initiatives():
    if InitiativeSection.query.first():
        return

    for raw_section_data in DEFAULT_INITIATIVES:
        section_data = dict(raw_section_data)
        subitems = section_data.pop('subitems', [])
        section = InitiativeSection(**section_data)
        db.session.add(section)
        db.session.flush()

        for index, title in enumerate(subitems, start=1):
            db.session.add(
                InitiativeSubitem(
                    section_id=section.id,
                    title=title,
                    order=index,
                    is_active=True,
                )
            )

    db.session.commit()



def get_donation_purpose_options(selected_purpose=''):

    options = [
        {
            'value': 'General Support',
            'label': 'General Support - Whole NGO',
        }
    ]
    seen = {'General Support'}

    sections = (
        InitiativeSection.query
        .filter_by(is_active=True)
        .order_by(InitiativeSection.order.asc(), InitiativeSection.id.asc())
        .all()
    )

    for section in sections:
        active_subitems = [item.title for item in section.subitems if item.is_active]
        option_value = active_subitems[0] if len(active_subitems) == 1 else section.title

        if option_value not in seen:
            options.append({
                'value': option_value,
                'label': option_value,
            })
            seen.add(option_value)

    if selected_purpose and selected_purpose not in seen:
        options.append({
            'value': selected_purpose,
            'label': selected_purpose,
        })

    return options


@app.context_processor
def inject_template_globals():
    return {
        'current_year': datetime.now().year,
        'accreditation_assets': {
            'iso': find_static_image_by_terms('iso'),
            'msme': find_static_image_by_terms('msme'),
        },
    }


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
        
    hero_slides_db = HeroSlide.query.filter_by(is_active=True).order_by(HeroSlide.order.asc()).all()
    hero_slides = [_serialize_hero_slide(slide) for slide in hero_slides_db]

    member_stories = MemberStory.query.filter_by(is_active=True).order_by(MemberStory.order.asc()).all()

    return render_template('index.html', home_slides=home_slides, hero_slides=hero_slides, member_stories=member_stories)


@app.route('/impacts')
def impacts():
    return render_template('impacts.html', impact_sections=IMPACT_PAGE_SECTIONS)


@app.route('/join-member')
def join_member():
    return render_template('join_member.html', membership_sections=JOIN_MEMBER_HIGHLIGHTS)


@app.route('/initiatives')
def initiatives():
    sections = (
        InitiativeSection.query
        .filter_by(is_active=True)
        .order_by(InitiativeSection.order.asc(), InitiativeSection.id.asc())
        .all()
    )
    
    # Pre-fetch dynamic images from Cloudinary for all featured sections
    initiative_images = {}
    for section in sections:
        if section.display_style == 'feature':
            folder_path = f'anchor/initiatives/{section.slug}'
            images = get_cloudinary_folder_images(folder_path, max_results=5)
            if images:
                initiative_images[section.slug] = images
            
    featured_sections = [section for section in sections if section.display_style == 'feature']
    list_sections = [section for section in sections if section.display_style == 'list']
    return render_template(
        'initiatives.html',
        sections=sections,
        featured_sections=featured_sections,
        list_sections=list_sections,
        initiative_images=initiative_images,
    )


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
    donation_purpose = request.args.get('purpose', '').strip()
    donation_options = get_donation_purpose_options(donation_purpose)
    return render_template(
        'donate.html',
        rzp_key=rzp_key_id,
        donation_purpose=donation_purpose,
        donation_options=donation_options,
    )


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


# --- Admin Login / Logout ---


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        user = AdminUser.query.filter_by(username=username).first()
        
        if user and user.is_active and user.check_password(password):
            session['admin_logged_in'] = True
            session['admin_username'] = user.username
            next_url = request.args.get('next', url_for('admin.index'))
            return redirect(next_url)
        error = 'Invalid credentials or inactive account.'
    return render_template('admin_login.html', error=error)


@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))


# Create tables for local/dev runs. Skip automatic bootstrap on Vercel because
# the deployed filesystem is read-only and import-time writes can crash startup.
with app.app_context():
    if should_bootstrap_database():
        db.create_all()
        seed_default_initiatives()

    else:
        app.logger.info('Skipping automatic database bootstrap in Vercel runtime.')


# --- CLI Commands ---
import click

@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin(username, password):
    """Create a new admin user or reset password for an existing one."""
    with app.app_context():
        user = AdminUser.query.filter_by(username=username).first()
        if user:
            user.set_password(password)
            db.session.commit()
            print(f"Password reset for admin: {username}")
        else:
            new_admin = AdminUser(username=username)
            new_admin.set_password(password)
            db.session.add(new_admin)
            db.session.commit()
            print(f"Created new admin user: {username}")


if __name__ == '__main__':
    app.run(debug=False)
