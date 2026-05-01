from markupsafe import Markup
from flask import request, redirect, url_for, session, flash
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.contrib.sqla import ModelView
from flask_wtf import FlaskForm
from wtforms import FileField, PasswordField, ValidationError, SelectField, MultipleFileField, SubmitField
import cloudinary.uploader
try:
    from .models import (
        HeroSlide,
        GalleryImage,
        TeamMember,
        AdminUser,
        InitiativeSection,
        InitiativeSubitem,
        MemberStory,
    )
except ImportError:
    from models import (
        HeroSlide,
        GalleryImage,
        TeamMember,
        AdminUser,
        InitiativeSection,
        InitiativeSubitem,
        MemberStory,
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
    @expose('/')
    def index(self):
        try:
            # We import db here to avoid circular dependencies
            from models import db
            db.create_all()
            flash("Database tables synchronized successfully.", "success")
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
        try:
            if hasattr(storage, 'stream') and hasattr(storage.stream, 'seek'):
                storage.stream.seek(0)

            result = cloudinary.uploader.upload(
                storage,
                folder=self.upload_folder,
                resource_type='image',
                use_filename=True,
                unique_filename=True,
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


class GalleryImageView(CloudinaryUploadView):
    upload_column = 'image_url'
    upload_folder = 'anchor/admin/gallery'
    upload_required = True
    column_list = ['id', 'image_url', 'category', 'alt_text']
    column_sortable_list = ['category']
    form_columns = ['upload_file', 'category', 'alt_text']


class TeamMemberView(CloudinaryUploadView):
    upload_column = 'image_url'
    upload_folder = 'anchor/admin/team'
    column_list = ['id', 'name', 'position', 'is_leader', 'order']
    column_sortable_list = ['name', 'order', 'is_leader']
    column_default_sort = 'order'
    form_columns = ['name', 'position', 'upload_file', 'speech', 'is_leader', 'order']


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


def setup_admin(app, db):
    """Initialize Flask-Admin with secure model views."""
    admin = Admin(
        app,
        name='Anchor Admin',
        index_view=SecureAdminIndex()
    )
    admin.add_view(HeroSlideView(HeroSlide, db.session, name='Hero Slides'))
    admin.add_view(GalleryImageView(GalleryImage, db.session, name='Gallery'))
    admin.add_view(TeamMemberView(TeamMember, db.session, name='Team'))
    admin.add_view(InitiativeSectionView(InitiativeSection, db.session, name='Initiatives'))
    admin.add_view(InitiativeSubitemView(InitiativeSubitem, db.session, name='Initiative Items'))
    admin.add_view(AdminUserView(AdminUser, db.session, name='Admins'))
    admin.add_view(MemberStoryView(MemberStory, db.session, name='Guided by Purpose'))
    admin.add_view(GalleryUploadView(name='Bulk Photo Upload', endpoint='bulk_upload'))
    admin.add_view(SyncDatabaseView(name='Sync Database', endpoint='sync-db'))
