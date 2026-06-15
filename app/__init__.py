import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from dotenv import load_dotenv
from flask_wtf import CSRFProtect
csrf = CSRFProtect()



# Load environment variables from .env (DB credentials, secret keys, etc.)
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()



def create_app():
    import os
    app = Flask(__name__)
    csrf.init_app(app)
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object("app.config.Config")

    

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'routes.login'
    login_manager.login_message_category = "info"

    # Register blueprints or routes
    from app import routes
    app.register_blueprint(routes.bp)
    from app import filters  # ✅ Import your custom filter module
    app.jinja_env.filters["localtime"] = filters.localtime  # ✅ Register filter
    from app.routes import register_filters
    register_filters(app)

    return app
