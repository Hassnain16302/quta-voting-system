import os

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change_me_to_a_random_string")
    # MySQL Database URI
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 10,
    "max_overflow": 5,
    "pool_timeout": 30,
    "pool_recycle": 1800
}


    # Mail settings (for sending user credentials)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    # OTP / Token expiration (in seconds)
    OTP_EXPIRATION = 300  # 5 minutes

    # Blockchain / Ganache
    GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")
    CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")  # will be set after deployment
