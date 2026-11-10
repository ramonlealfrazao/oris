"""Model Auditoria."""

from app.extensions import db
from app.utils.datetime_utils import utcnow


class Auditoria(db.Model):
    __tablename__ = "auditorias"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,  # tentativa de login com usuario inexistente nao tem usuario
        index=True,
    )

    acao = db.Column(db.String(100), nullable=False)

    tabela = db.Column(db.String(100), nullable=True)

    registro_id = db.Column(db.Integer, nullable=True)

    descricao = db.Column(db.Text, nullable=True)

    valor_anterior = db.Column(db.Text, nullable=True)
    valor_novo = db.Column(db.Text, nullable=True)

    data_hora = db.Column(db.DateTime, nullable=False, default=utcnow)

    # DE ONDE e RESULTADO (elementos obrigatorios de um audit trail).
    origem_ip = db.Column(db.String(45), nullable=True)  # 45 = IPv6 completo
    resultado = db.Column(db.String(10), nullable=False, default="SUCESSO", server_default="SUCESSO")
    # So para LOGIN_FALHA/LOGIN_BLOQUEADO: o identificador digitado (nunca a senha).
    identificador_tentado = db.Column(db.String(255), nullable=True)


    usuario = db.relationship("Usuario", back_populates="auditorias")

    def __repr__(self):
        return f"<Auditoria id={self.id} acao={self.acao} usuario_id={self.usuario_id}>"
