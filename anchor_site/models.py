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
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<HeroSlide {self.title}>'


class AchievementSlide(db.Model):
    __tablename__ = 'achievement_slides'

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    button_text = db.Column(db.String(80))
    button_link = db.Column(db.String(300))
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<AchievementSlide {self.title}>'


class GalleryImage(db.Model):
    __tablename__ = 'gallery_images'

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), default='general')
    alt_text = db.Column(db.String(300))
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<GalleryImage {self.id} - {self.category}>'


class ImpactMetric(db.Model):
    __tablename__ = 'impact_metrics'

    id = db.Column(db.Integer, primary_key=True)
    icon = db.Column(db.String(80), default='users')
    number = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<ImpactMetric {self.title}>'




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
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)
    image_on_right = db.Column(db.Boolean, default=False)

    subitems = db.relationship(
        'InitiativeSubitem',
        back_populates='section',
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
    section = db.relationship('InitiativeSection', back_populates='subitems')
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<InitiativeSubitem {self.title}>'


class MemberStory(db.Model):
    """A 'Guided by Purpose' split-screen card shown on the homepage.

    Each record renders as a 50/50 layout: scrollable green text column
    on the left and a full-bleed portrait on the right.
    """
    __tablename__ = 'member_stories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    qualification = db.Column(db.String(300), default='')
    role_tag = db.Column(db.String(120), default='Our Member')
    body_html = db.Column(db.Text, nullable=False, default='')
    portrait_url = db.Column(db.String(500), default='')
    order = db.Column('order', db.Integer, default=0, quote=True)
    is_active = db.Column(db.Boolean, default=True)
    image_on_right = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<MemberStory {self.name}>'


class CommunityMember(db.Model):
    """A small community member card shown in the queue section."""
    __tablename__ = 'community_members'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    qualification = db.Column(db.String(300), default='')
    photo_url = db.Column(db.String(500), default='')
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<CommunityMember {self.name}>'
