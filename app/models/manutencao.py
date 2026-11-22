from app.extensions import db
from app.models.mixins import TimestampMixin

TIPOS_MANUTENCAO = ("PREVENTIVA", "CORRETIVA")
SITUACOES_MANUTENCAO = ("ABERTA", "CONCLUIDA", "CANCELADA")


class Manutencao(db.Model, TimestampMixin):
    __tablename__ = "manutencoes"

    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(
        db.Integer,
        db.ForeignKey("equipamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(db.Enum(*TIPOS_MANUTENCAO, name="tipo_manutencao_enum"), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    data_abertura = db.Column(db.Date, nullable=False)
    data_conclusao = db.Column(db.Date, nullable=True)
    custo = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    situacao = db.Column(
        db.Enum(*SITUACOES_MANUTENCAO, name="situacao_manutencao_enum"),
        nullable=False,
        default="ABERTA",
    )

    equipamento = db.relationship("Equipamento", backref=db.backref("manutencoes", passive_deletes=True))

    def __repr__(self):
        return f"<Manutencao id={self.id} equipamento_id={self.equipamento_id} {self.situacao}>"
