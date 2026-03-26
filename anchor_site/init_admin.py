import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from .app import app, db
    from .models import AdminUser
except ImportError:
    from app import app, db
    from models import AdminUser

with app.app_context():
    # Ensure tables are created if this runs before app is loaded
    db.create_all()
    
    username = sys.argv[1] if len(sys.argv) > 1 else 'admin'
    password = sys.argv[2] if len(sys.argv) > 2 else 'anchor2026'
    
    existing = AdminUser.query.filter_by(username=username).first()
    if existing:
        print(f"User '{username}' already exists.")
        existing.set_password(password)
        db.session.commit()
        print(f"Password reset for '{username}'.")
    else:
        new_admin = AdminUser(username=username)
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()
        print(f"Created new admin user: {username}")
