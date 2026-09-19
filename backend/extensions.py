"""
Extensions are created here, unbound, and attached to the app in app.py
via init_app(). This avoids circular imports between models/routes/app.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()

limiter = Limiter(key_func=get_remote_address)
