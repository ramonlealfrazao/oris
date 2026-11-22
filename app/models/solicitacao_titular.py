from app.extensions import db
from app.models.enums import StatusSolicitacaoTitular, TipoSolicitacaoTitular
from app.utils.datetime_utils import utcnow


class SolicitacaoTitular(db.Model):
    __tablename__ = "solicitacoes_titular"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)

    tipo = db.Column(db.Enum(TipoSolicitacaoTitular, name="tipo_solicitacao_titular_enum"), nullable=False)

    descricao = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(StatusSolicitacaoTitular, name="status_solicitacao_titular_enum"),
        nullable=False,
        default=StatusSolicitacaoTitular.ABERTA,
    )

    resposta = db.Column(db.Text, nullable=True)

    criada_em = db.Column(db.DateTime, nullable=False, default=utcnow)
    prazo_resposta = db.Column(db.DateTime, nullable=False)
    respondida_em = db.Column(db.DateTime, nullable=True)
    respondida_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    titular = db.relationship("Usuario", foreign_keys=[usuario_id])
    responsavel = db.relationship("Usuario", foreign_keys=[respondida_por])

    def __repr__(self):
        return f"<SolicitacaoTitular id={self.id} tipo={self.tipo} status={self.status}>"
