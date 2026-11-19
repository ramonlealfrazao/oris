"""Model Usuario."""

from app.extensions import db
from app.models.enums import OrigemDiretorio, PerfilUsuario
from app.models.grupo import usuario_grupos
from app.models.mixins import TimestampMixin


class Usuario(db.Model, TimestampMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)

    email = db.Column(db.String(150), nullable=False, unique=True, index=True)

    senha_hash = db.Column(db.String(255), nullable=False)

    perfil = db.Column(
        db.Enum(PerfilUsuario, name="perfil_usuario_enum"),
        nullable=False,
    )

    ativo = db.Column(db.Boolean, nullable=False, default=True)

    # Origem da conta: LOCAL (cadastrada no ORIS, autentica com senha
    # bcrypt) ou LDAP/OIDC (provisionada por app/services/
    # diretorio_service.py; nunca autentica com senha local).
    origem = db.Column(
        db.Enum(OrigemDiretorio, name="origem_usuario_enum"),
        nullable=False,
        default=OrigemDiretorio.LOCAL,
    )

    # Identificador estável no diretório externo (uid do LDAP ou `sub`
    # do OIDC). Nulo para contas LOCAL.
    identificador_externo = db.Column(db.String(255), nullable=True, index=True)

    # --- MFA (TOTP) do login local - app/services/mfa_service.py ---
    # Contas LDAP/OIDC fazem o segundo fator no provedor (Keycloak).
    mfa_ativo = db.Column(db.Boolean, nullable=False, default=False)
    # Segredo TOTP cifrado com DATA_ENCRYPTION_KEY (Fernet); nunca em texto puro.
    mfa_segredo = db.Column(db.Text, nullable=True)
    # Último intervalo de 30 s aceito: impede reusar o mesmo código (replay).
    mfa_ultimo_passo = db.Column(db.BigInteger, nullable=True)
    # JSON com o SHA-256 dos códigos de recuperação ainda não usados.
    mfa_codigos_recuperacao = db.Column(db.Text, nullable=True)

    # --- Relacionamentos ---

    grupos = db.relationship("Grupo", secondary=usuario_grupos, back_populates="usuarios")

    # Alterações criadas por este usuário (Fase 7 usa isso no fluxo).
    alteracoes_criadas = db.relationship(
        "Alteracao",
        back_populates="usuario_criador",
        foreign_keys="Alteracao.usuario_id",
        lazy="dynamic",
    )

    alteracoes_aprovadas = db.relationship(
        "Alteracao",
        back_populates="usuario_aprovador",
        foreign_keys="Alteracao.approved_by",
        lazy="dynamic",
    )

    auditorias = db.relationship(
        "Auditoria",
        back_populates="usuario",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Usuario id={self.id} email={self.email} perfil={self.perfil}>"
