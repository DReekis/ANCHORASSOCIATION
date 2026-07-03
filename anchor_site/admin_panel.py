import os
from markupsafe import Markup, escape
from flask import request, redirect, url_for, session, flash
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from flask_wtf import FlaskForm
from wtforms import FileField, PasswordField, ValidationError, SelectField, MultipleFileField, SubmitField
import cloudinary.uploader
try:
    from .models import (
        AchievementSlide,
        HeroSlide,
        GalleryImage,
        ImpactMetric,
        AdminUser,
        InitiativeSection,
        InitiativeSubitem,
        MemberStory,
        CommunityMember,
    )
except ImportError:
    from models import (
        AchievementSlide,
        HeroSlide,
        GalleryImage,
        ImpactMetric,
        AdminUser,
        InitiativeSection,
        InitiativeSubitem,
        MemberStory,
        CommunityMember,
    )


class AuthMixin:
    """Shared authentication logic for admin views."""

    def _is_authenticated(self):
        return session.get('admin_logged_in', False)

    def is_accessible(self):
        return self._is_authenticated()

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin_login', next=request.url))


class SecureAdminIndex(AuthMixin, AdminIndexView):
    @expose('/')
    def index(self):
        if not self._is_authenticated():
            return redirect(url_for('admin_login', next=request.url))
        return super().index()


class SyncDatabaseView(AuthMixin, BaseView):
    """Utility view to force sync database tables in production (Vercel)."""
    def __init__(self, db, **kwargs):
        super(SyncDatabaseView, self).__init__(**kwargs)
        self.db = db

    @expose('/')
    def index(self):
        try:
            from sqlalchemy import text
            self.db.create_all()
            
            # Manually add missing columns to existing tables for Postgres
            try:
                self.db.session.execute(text('ALTER TABLE initiative_sections ADD COLUMN IF NOT EXISTS image_on_right BOOLEAN DEFAULT FALSE'))
                self.db.session.execute(text('ALTER TABLE initiative_subitems ADD COLUMN IF NOT EXISTS description TEXT'))
                self.db.session.execute(text('ALTER TABLE member_stories ADD COLUMN IF NOT EXISTS image_on_right BOOLEAN DEFAULT TRUE'))
                self.db.session.execute(text('ALTER TABLE member_stories ADD COLUMN IF NOT EXISTS qualification VARCHAR(300) DEFAULT \'\''))
                self.db.session.execute(text('ALTER TABLE member_stories ADD COLUMN IF NOT EXISTS role_tag VARCHAR(120) DEFAULT \'Our Member\''))
                self.db.session.execute(text('ALTER TABLE gallery_images ADD COLUMN IF NOT EXISTS "order" INTEGER DEFAULT 0'))
                self.db.session.execute(text('ALTER TABLE gallery_images ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE'))
                self.db.session.commit()
            except Exception as e:
                self.db.session.rollback()
                # If IF NOT EXISTS fails or is unsupported (like in some sqlite versions), we ignore
                pass

            flash("Database tables and columns synchronized successfully.", "success")
        except Exception as e:
            flash(f"Error syncing database: {e}", "error")
        
        return redirect(url_for('admin.index'))


class SecureModelView(AuthMixin, ModelView):
    pass


class CloudinaryUploadView(SecureModelView):
    upload_field_name = 'upload_file'
    upload_column = None
    upload_folder = None
    upload_required = False
    upload_max_bytes = 10 * 1024 * 1024
    upload_allowed_mimetypes = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    form_extra_fields = {
        'upload_file': FileField('Browse File')
    }

    def _get_uploaded_file(self, form):
        upload_field = getattr(form, self.upload_field_name, None)
        if not upload_field:
            return None

        storage = upload_field.data
        if storage is None:
            return None

        filename = (getattr(storage, 'filename', '') or '').strip()
        if not filename:
            return None

        return storage

    def _upload_to_cloudinary(self, storage):
        mimetype = (getattr(storage, 'mimetype', '') or '').lower()
        if mimetype and mimetype not in self.upload_allowed_mimetypes:
            raise ValidationError('Please upload a JPG, PNG, WebP, or GIF image.')

        if hasattr(storage, 'stream') and hasattr(storage.stream, 'seek'):
            storage.stream.seek(0)
            storage.stream.seek(0, os.SEEK_END)
            size = storage.stream.tell()
            storage.stream.seek(0)
            if size > self.upload_max_bytes:
                raise ValidationError('Please upload an image smaller than 10MB.')

        try:
            if hasattr(storage, 'stream') and hasattr(storage.stream, 'seek'):
                storage.stream.seek(0)

            result = cloudinary.uploader.upload(
                storage,
                folder=self.upload_folder,
                resource_type='image',
                use_filename=True,
                unique_filename=True,
                allowed_formats=['jpg', 'jpeg', 'png', 'webp', 'gif'],
                eager=[
                    {
                        'width': 1920,
                        'height': 1080,
                        'crop': 'fill',
                        'gravity': 'auto',
                        'quality': 'auto:good',
                        'fetch_format': 'auto',
                    },
                    {
                        'width': 1200,
                        'height': 800,
                        'crop': 'fill',
                        'gravity': 'auto',
                        'quality': 'auto:good',
                        'fetch_format': 'auto',
                    },
                    {
                        'width': 720,
                        'height': 540,
                        'crop': 'fill',
                        'gravity': 'auto',
                        'quality': 'auto:good',
                        'fetch_format': 'auto',
                    },
                ],
                eager_async=False,
            )
        except Exception as exc:
            raise ValidationError(f'Cloudinary upload failed: {exc}')

        secure_url = result.get('secure_url')
        if not secure_url:
            raise ValidationError('Cloudinary upload did not return a secure URL.')

        return secure_url

    def on_model_change(self, form, model, is_created):
        storage = self._get_uploaded_file(form)

        if storage:
            setattr(model, self.upload_column, self._upload_to_cloudinary(storage))
        elif is_created and self.upload_required and not getattr(model, self.upload_column, None):
            raise ValidationError('Please choose a file to upload before saving.')

        super().on_model_change(form, model, is_created)


def _image_preview(view, context, model, name):
    image_url = getattr(model, name, '') or getattr(model, 'image_url', '') or ''
    if not image_url:
        return ''

    return Markup(
        '<img src="{0}" alt="" style="width:72px;height:52px;object-fit:cover;'
        'border-radius:10px;border:1px solid rgba(0,0,0,.08);'
        'box-shadow:0 6px 14px rgba(0,0,0,.08)">'
        .format(escape(image_url))
    )


class HeroSlideView(CloudinaryUploadView):
    upload_column = 'image_url'
    upload_folder = 'anchor/admin/hero-slides'
    upload_required = True
    column_list = ['id', 'title', 'subtitle', 'order', 'is_active']
    column_labels = {
        'upload_file': 'Browse File',
    }
    column_sortable_list = ['order', 'title', 'is_active']
    column_default_sort = 'order'
    form_columns = ['upload_file', 'title', 'subtitle', 'order', 'is_active']
    form_args = {
        'title': {
            'description': 'Keep headlines concise. The hero clamps long titles to two lines on the site.',
            'render_kw': {
                'maxlength': 120,
                'placeholder': 'Short headline for the slide',
            },
        },
        'subtitle': {
            'description': 'Optional supporting copy. Best around 120-160 characters. Recommended hero artwork ratio: 16:9.',
            'render_kw': {
                'maxlength': 220,
                'placeholder': 'Optional supporting copy for the slide',
            },
        },
        'order': {
            'description': 'Lower numbers appear first in the slideshow.',
        },
    }


class AchievementSlideView(CloudinaryUploadView):
    upload_column = 'image_url'
    upload_folder = 'anchor/admin/achievements'
    upload_required = True
    column_list = ['id', 'order', 'image_url', 'title', 'button_text', 'is_active']
    column_labels = {
        'image_url': 'Preview',
        'upload_file': 'Achievement Image',
        'button_text': 'Button Text',
        'button_link': 'Button Link',
        'is_active': 'Active',
    }
    column_formatters = {
        'image_url': _image_preview,
    }
    column_sortable_list = ['order', 'title', 'is_active']
    column_default_sort = 'order'
    form_columns = [
        'upload_file',
        'title',
        'description',
        'button_text',
        'button_link',
        'order',
        'is_active',
    ]
    form_args = {
        'upload_file': {
            'description': 'Recommended image: a wide photo at least 1600px wide. The site crops it intelligently for desktop and mobile.',
        },
        'title': {
            'description': 'Short success-story headline.',
            'render_kw': {
                'maxlength': 120,
                'placeholder': 'e.g. Learning support reached new villages',
            },
        },
        'description': {
            'description': 'Two or three calm sentences. Keep it easy for visitors to scan.',
            'render_kw': {
                'rows': 4,
                'placeholder': 'Briefly describe the achievement.',
            },
        },
        'button_text': {
            'description': 'Optional. Leave blank to hide the button.',
            'render_kw': {'placeholder': 'Read more'},
        },
        'button_link': {
            'description': 'Optional. Use a full URL or a site path such as /donate.',
            'render_kw': {'placeholder': '/donate'},
        },
        'order': {
            'description': 'Lower numbers appear first in the slideshow.',
        },
    }


class GalleryImageView(CloudinaryUploadView):
    upload_column = 'image_url'
    upload_folder = 'anchor/admin/gallery'
    upload_required = True
    column_list = ['id', 'order', 'image_url', 'category', 'alt_text', 'is_active']
    column_labels = {
        'image_url': 'Preview',
        'upload_file': 'Gallery Image',
        'alt_text': 'Alt Text',
        'is_active': 'Visible',
    }
    column_formatters = {
        'image_url': _image_preview,
    }
    column_sortable_list = ['order', 'category', 'is_active']
    column_default_sort = 'order'
    form_columns = ['upload_file', 'category', 'alt_text', 'order', 'is_active']
    form_args = {
        'category': {
            'description': 'Optional grouping label, such as Education, Health, Community, or Events.',
            'render_kw': {'placeholder': 'Community'},
        },
        'alt_text': {
            'description': 'Describe what is in the photo for accessibility.',
            'render_kw': {'placeholder': 'Students in an Anchor classroom session'},
        },
        'order': {
            'description': 'Lower numbers appear earlier in the home gallery.',
        },
    }


class ImpactMetricView(SecureModelView):
    column_list = ['id', 'order', 'icon', 'number', 'title', 'is_active']
    column_labels = {
        'number': 'Number',
        'is_active': 'Visible',
    }
    column_sortable_list = ['order', 'title', 'is_active']
    column_default_sort = 'order'
    form_columns = ['icon', 'number', 'title', 'description', 'order', 'is_active']
    form_choices = {
        'icon': [
            ('users', 'Community / People'),
            ('book-open', 'Education'),
            ('heart', 'Care / Health'),
            ('leaf', 'Environment'),
            ('award', 'Recognition'),
            ('briefcase', 'Livelihood'),
        ],
    }
    form_args = {
        'number': {
            'description': 'The large value shown on the card, such as 1,000+ or 2019.',
            'render_kw': {'placeholder': '1,000+'},
        },
        'title': {
            'description': 'Short card title.',
            'render_kw': {'placeholder': 'Learners supported'},
        },
        'description': {
            'description': 'One concise sentence explaining the number.',
            'render_kw': {
                'rows': 3,
                'placeholder': 'A short supporting line for this impact metric.',
            },
        },
        'order': {
            'description': 'Lower numbers appear first.',
        },
    }





def _format_layout_direction(view, context, model, name):
    """Custom column formatter: shows layout direction as a readable label."""
    if model.image_on_right:
        return Markup('<span style="white-space:nowrap">🖼️ Image Right | 📝 Text Left</span>')
    return Markup('<span style="white-space:nowrap">🖼️ Image Left | 📝 Text Right</span>')


class InitiativeSectionView(CloudinaryUploadView):
    upload_column = 'media_url'
    upload_folder = 'anchor/admin/initiatives'
    column_list = [
        'id',
        'order',
        'title',
        'display_style',
        'image_on_right',
        'impact_value',
        'cta_label',
        'is_active',
    ]
    column_labels = {
        'order': 'Section Number',
        'impact_label': 'Number Label',
        'impact_value': 'Displayed Number',
        'upload_file': 'Browse File',
        'cta_label': 'Button Label',
        'cta_url': 'Button Link',
        'media_url': 'Image / Media URL',
        'media_alt': 'Image Alt Text',
        'display_style': 'Layout Style',
        'image_on_right': 'Image Position',
    }
    column_formatters = {
        'image_on_right': _format_layout_direction,
    }
    column_sortable_list = ['order', 'title', 'display_style', 'is_active']
    column_default_sort = 'order'
    form_columns = [
        'slug',
        'title',
        'summary',
        'description',
        'impact_label',
        'impact_value',
        'cta_label',
        'cta_url',
        'upload_file',
        'media_alt',
        'theme',
        'display_style',
        'order',
        'is_active',
        'image_on_right',
    ]
    form_args = {
        'image_on_right': {
            'description': 'Check this box to put the photo on the right. Leave unchecked for Image Left.',
        },
    }


class InitiativeSubitemView(SecureModelView):
    column_list = ['id', 'section', 'title', 'order', 'is_active']
    column_labels = {
        'section': 'Parent Initiative',
        'order': 'Item Number',
    }
    column_sortable_list = ['title', 'order', 'is_active']
    column_default_sort = 'order'
    form_columns = ['section', 'title', 'description', 'order', 'is_active']


class AdminUserView(SecureModelView):
    column_list = ['id', 'username', 'is_active']
    column_searchable_list = ['username']
    form_columns = ['username', 'new_password', 'is_active']
    
    # Render a password field instead of plain text
    form_extra_fields = {
        'new_password': PasswordField('New Password (leave blank to keep current)')
    }

    def on_model_change(self, form, model, is_created):
        if form.new_password.data:
            model.set_password(form.new_password.data)


class InitiativeGalleryForm(FlaskForm):
    initiative = SelectField('Initiative Folder', choices=[])
    photos = MultipleFileField('Select Photos')
    submit = SubmitField('Upload Bulk Photos')


class GalleryUploadView(AuthMixin, BaseView):
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if not self._is_authenticated():
            return redirect(url_for('admin_login', next=request.url))
            
        form = InitiativeGalleryForm()
        sections = InitiativeSection.query.order_by(InitiativeSection.title).all()
        form.initiative.choices = [(s.slug, s.title) for s in sections]
        
        if request.method == 'POST' and form.validate_on_submit():
            uploaded_files = request.files.getlist(form.photos.name)
            success_count = 0
            initiative_slug = form.initiative.data
            folder_path = f"anchor/initiatives/{initiative_slug}"
            
            for file in uploaded_files:
                if file and file.filename:
                    try:
                        cloudinary.uploader.upload(
                            file,
                            folder=folder_path,
                            resource_type='image',
                            use_filename=True,
                            unique_filename=True
                        )
                        success_count += 1
                    except Exception as exc:
                        flash(f'Failed to upload {file.filename}: {exc}', 'error')
                        
            if success_count > 0:
                choice_label = dict(form.initiative.choices).get(initiative_slug, initiative_slug)
                flash(f'Successfully uploaded {success_count} photos to {choice_label}.', 'success')
                
            return redirect(url_for('.index'))
            
        return self.render('admin/gallery_upload.html', form=form)


class MemberStoryView(CloudinaryUploadView):
    """Admin view for the 'Guided by Purpose' split-screen member cards."""
    upload_column = 'portrait_url'
    upload_folder = 'anchor/admin/member-stories'
    column_list = ['id', 'order', 'name', 'role_tag', 'image_on_right', 'is_active']
    column_labels = {
        'name': 'Member Name',
        'qualification': 'Qualification / Designation',
        'role_tag': 'Eyebrow Label',
        'body_html': 'Story Content (HTML)',
        'portrait_url': 'Portrait Image URL',
        'upload_file': 'Upload Portrait',
        'order': 'Display Order',
        'image_on_right': 'Image Position',
    }
    column_formatters = {
        'image_on_right': _format_layout_direction,
    }
    column_sortable_list = ['order', 'name', 'is_active']
    column_default_sort = 'order'
    form_columns = [
        'name',
        'qualification',
        'role_tag',
        'body_html',
        'upload_file',
        'image_on_right',
        'order',
        'is_active',
    ]
    form_args = {
        'name': {
            'description': 'Full name shown as the large heading on the green panel (e.g. "Mousumi Dey").',
            'render_kw': {'placeholder': 'e.g. Mousumi Dey'},
        },
        'qualification': {
            'description': 'Appears directly under the name (e.g. "B.Sc.(Hons), LLB (Hons), MSW").',
            'render_kw': {'placeholder': 'e.g. B.Sc.(Hons), LLB (Hons), MSW'},
        },
        'role_tag': {
            'description': 'Small uppercase label above the name (e.g. "Our Founder", "Our Treasurer").',
            'render_kw': {'placeholder': 'e.g. Our Founder'},
        },
        'body_html': {
            'description': (
                'Wrap each paragraph in <p>...</p> tags. '
                'This text fills the scrollable green column beside the portrait.'
            ),
        },
        'image_on_right': {
            'description': 'Check this box to put the photo on the right. Leave unchecked for Image Left.',
        },
        'order': {
            'description': 'Lower numbers appear first. Each entry becomes a full-width 50/50 split section.',
        },
    }


class CommunityMemberView(CloudinaryUploadView):
    """Admin view for the community members queue."""
    upload_column = 'photo_url'
    upload_folder = 'anchor/admin/community-members'
    column_list = ['id', 'name', 'qualification', 'is_active']
    column_labels = {
        'photo_url': 'Photo URL',
        'upload_file': 'Upload Photo',
    }
    column_sortable_list = ['name', 'is_active']
    form_columns = [
        'name',
        'qualification',
        'upload_file',
        'is_active',
    ]


def _patch_wtforms_tuple_bug():
    try:
        import flask_admin.contrib.sqla.validators as sqla_validators
        if hasattr(sqla_validators.Unique, 'field_flags') and isinstance(sqla_validators.Unique.field_flags, tuple):
            sqla_validators.Unique.field_flags = {k: True for k in sqla_validators.Unique.field_flags}
            
        import flask_admin.form.validators as form_validators
        for name in dir(form_validators):
            obj = getattr(form_validators, name)
            if hasattr(obj, 'field_flags') and isinstance(obj.field_flags, tuple):
                obj.field_flags = {k: True for k in obj.field_flags}
    except Exception:
        pass


def setup_admin(app, db):
    """Initialize Flask-Admin with secure model views."""
    _patch_wtforms_tuple_bug()
    
    admin = Admin(
        app,
        name='Anchor Admin',
        index_view=SecureAdminIndex(),
        url='/anchor-dashboard-x7k9p2'
    )
    admin.add_view(HeroSlideView(HeroSlide, db.session, name='Hero Slides'))
    admin.add_view(AchievementSlideView(AchievementSlide, db.session, name='Achievements'))
    admin.add_view(ImpactMetricView(ImpactMetric, db.session, name='Impact Metrics'))
    admin.add_view(GalleryImageView(GalleryImage, db.session, name='Gallery'))
    admin.add_view(InitiativeSectionView(InitiativeSection, db.session, name='Initiatives'))
    admin.add_view(InitiativeSubitemView(InitiativeSubitem, db.session, name='Initiative Items'))
    admin.add_view(AdminUserView(AdminUser, db.session, name='Admins'))
    admin.add_view(MemberStoryView(MemberStory, db.session, name='Guided by Purpose'))
    admin.add_view(CommunityMemberView(CommunityMember, db.session, name='Community Members'))
    admin.add_view(GalleryUploadView(name='Bulk Photo Upload', endpoint='bulk_upload'))
    admin.add_view(SyncDatabaseView(db, name='Sync Database', endpoint='sync-db'))
    admin.add_link(MenuLink(name='Logout', url='/anchor-exit-x7k9p2'))
