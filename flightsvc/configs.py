

class DevConfig:
    DEBUG = True
    ENV = "development"
    SQLALCHEMY_DATABASE_URI = 'sqlite:///flightsvc.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False