from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class AdminUser(db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<AdminUser {self.username}>'


class HeroSlide(db.Model):
    __tablename__ = 'hero_slides'

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300))
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<HeroSlide {self.title}>'


class GalleryImage(db.Model):
    __tablename__ = 'gallery_images'

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), default='general')
    alt_text = db.Column(db.String(300))

    def __repr__(self):
        return f'<GalleryImage {self.id} - {self.category}>'


class TeamMember(db.Model):
    __tablename__ = 'team_members'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    position = db.Column(db.String(200))
    image_url = db.Column(db.String(500))
    speech = db.Column(db.Text)
    is_leader = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<TeamMember {self.name}>'


class InitiativeSection(db.Model):
    __tablename__ = 'initiative_sections'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(300))
    description = db.Column(db.Text)
    impact_label = db.Column(db.String(100), default='Beneficiaries')
    impact_value = db.Column(db.String(100), default='1000+')
    cta_label = db.Column(db.String(80))
    cta_url = db.Column(db.String(300))
    media_url = db.Column(db.String(500))
    media_alt = db.Column(db.String(300))
    theme = db.Column(db.String(40), default='forest')
    display_style = db.Column(db.String(40), default='feature')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    subitems = db.relationship(
        'InitiativeSubitem',
        backref='section',
        lazy='select',
        cascade='all, delete-orphan',
        order_by='InitiativeSubitem.order'
    )

    def __repr__(self):
        return f'<InitiativeSection {self.title}>'

    def __str__(self):
        return self.title


class InitiativeSubitem(db.Model):
    __tablename__ = 'initiative_subitems'

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(
        db.Integer,
        db.ForeignKey('initiative_sections.id'),
        nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<InitiativeSubitem {self.title}>'
