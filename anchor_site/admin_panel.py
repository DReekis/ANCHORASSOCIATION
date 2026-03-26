from flask import request, redirect, url_for, session
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from wtforms import FileField, PasswordField, ValidationError
import cloudinary.uploader

try:
    from .models import (
        HeroSlide,
        GalleryImage,
        TeamMember,
        AdminUser,
        InitiativeSection,
        InitiativeSubitem,
    )
except ImportError:
    from models import (
        HeroSlide,
        GalleryImage,
        TeamMember,
        AdminUser,
        InitiativeSection,
        InitiativeSubitem,
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
    column_sortable_list = ['order', 'title', 'is_active']
    column_default_sort = 'order'
    form_columns = ['upload_file', 'title', 'subtitle', 'order', 'is_active']


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


class InitiativeSectionView(CloudinaryUploadView):
    upload_column = 'media_url'
    upload_folder = 'anchor/admin/initiatives'
    column_list = [
        'id',
        'order',
        'title',
        'display_style',
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
    ]


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
