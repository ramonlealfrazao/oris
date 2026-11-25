import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY_PADRAO = "dev-key-insegura-trocar-no-env"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", SECRET_KEY_PADRAO)
    DATA_ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY", "")

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "oris_db")
    DB_USER = os.getenv("DB_USER", "oris_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_LIFETIME_MINUTES = int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)

    TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))

    LGPD_CONTROLADOR = os.getenv("LGPD_CONTROLADOR", "Secretaria de Saúde do Recife")
    LGPD_ENCARREGADO_NOME = os.getenv("LGPD_ENCARREGADO_NOME", "")
    LGPD_ENCARREGADO_EMAIL = os.getenv("LGPD_ENCARREGADO_EMAIL", "")
    LGPD_BASE_LEGAL = os.getenv(
        "LGPD_BASE_LEGAL",
        "Execução de políticas públicas pela administração pública (LGPD, art. 7º, III, e art. 23).",
    )
    LGPD_RETENCAO_AUDITORIA_ANOS = int(os.getenv("LGPD_RETENCAO_AUDITORIA_ANOS", "1"))
    LGPD_PRAZO_RESPOSTA_DIAS = int(os.getenv("LGPD_PRAZO_RESPOSTA_DIAS", "15"))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_ENABLED = True

    RATE_LIMIT_LOGIN_ENABLED = True

    MFA_OBRIGATORIO = os.getenv("MFA_OBRIGATORIO", "true").strip().lower() == "true"

    DIRETORIO_MAPA_GRUPO_PERFIL = os.getenv("DIRETORIO_MAPA_GRUPO_PERFIL", "{}")

    LDAP_URI = os.getenv("LDAP_URI", "")
    LDAP_USE_STARTTLS = os.getenv("LDAP_USE_STARTTLS", "false").lower() == "true"
    LDAP_ALLOW_INSECURE = os.getenv("LDAP_ALLOW_INSECURE", "false").lower() == "true"
    LDAP_CA_CERT_FILE = os.getenv("LDAP_CA_CERT_FILE", "")
    LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")
    LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", "")
    LDAP_USER_FILTER = os.getenv("LDAP_USER_FILTER", "(objectClass=person)")
    LDAP_GROUP_BASE = os.getenv("LDAP_GROUP_BASE", "")
    LDAP_GROUP_FILTER = os.getenv("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")
    LDAP_ATTR_ID = os.getenv("LDAP_ATTR_ID", "uid")
    LDAP_ATTR_NOME = os.getenv("LDAP_ATTR_NOME", "cn")
    LDAP_ATTR_EMAIL = os.getenv("LDAP_ATTR_EMAIL", "mail")
    LDAP_ATTR_GROUP_NAME = os.getenv("LDAP_ATTR_GROUP_NAME", "cn")
    LDAP_ATTR_GROUP_MEMBER = os.getenv("LDAP_ATTR_GROUP_MEMBER", "member")

    OIDC_ENABLED = os.getenv("OIDC_ENABLED", "false").lower() == "true"
    OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")
    OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid profile email")
    OIDC_CLAIM_GROUPS = os.getenv("OIDC_CLAIM_GROUPS", "groups")
    OIDC_CLAIM_LDAP_UID = os.getenv("OIDC_CLAIM_LDAP_UID", "")
    OIDC_PROMPT = os.getenv("OIDC_PROMPT", "login")
    OIDC_ALLOW_INSECURE = os.getenv("OIDC_ALLOW_INSECURE", "false").lower() == "true"

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_SA_ARQUIVO = os.getenv("GOOGLE_SA_ARQUIVO", "")
    GOOGLE_DRIVE_PASTA_ID = os.getenv("GOOGLE_DRIVE_PASTA_ID", "")

    S3_BUCKET = os.getenv("S3_BUCKET", "")
    S3_REGION = os.getenv("S3_REGION", "")
    S3_PREFIX = os.getenv("S3_PREFIX", "oris/relatorios")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
    S3_URL_EXPIRA_SEGUNDOS = int(os.getenv("S3_URL_EXPIRA_SEGUNDOS", "900"))


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").strip().lower() != "false"


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    RATE_LIMIT_LOGIN_ENABLED = False
    MFA_OBRIGATORIO = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DATA_ENCRYPTION_KEY = "8YUlDwN5PXNRQGa8BFCUZkwAA95sjPiITg3aJ8u0MZs="


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)
