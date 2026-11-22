from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Regexp, ValidationError

CNES_REGEX = r"^\d{7,15}$"


def _descricao_situacao_obrigatoria(form, field):
    situacao = form.situacao.data
    if situacao in {"INATIVA", "INATIVO", "MANUTENCAO"} and not (field.data or "").strip():
        raise ValidationError("Informe a descrição para essa situação.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Informe o email."),
            Email(message="Email inválido.", check_deliverability=False),
        ],
    )
    senha = PasswordField(
        "Senha",
        validators=[DataRequired(message="Informe a senha."), Length(min=1, max=255)],
    )
    submit = SubmitField("Entrar")


class MfaCodigoForm(FlaskForm):
    codigo = StringField(
        "Código",
        validators=[DataRequired(message="Informe o código."), Length(min=6, max=20, message="Código inválido.")],
    )
    submit = SubmitField("Confirmar")


class UnidadeForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome da unidade."), Length(max=200)],
    )

    cnes = StringField(
        "CNES",
        validators=[
            DataRequired(message="Informe o código CNES."),
            Regexp(
                CNES_REGEX,
                message="CNES deve conter apenas números (entre 7 e 15 dígitos).",
            ),
        ],
    )

    tipo = StringField(
        "Tipo",
        validators=[DataRequired(message="Informe o tipo da unidade."), Length(max=100)],
    )

    endereco = StringField("Endereço", validators=[Length(max=255)])
    bairro = StringField("Bairro", validators=[Length(max=100)])

    cidade = StringField(
        "Cidade",
        validators=[DataRequired(message="Informe a cidade."), Length(max=100)],
    )

    uf = StringField(
        "UF",
        validators=[
            DataRequired(message="Informe a UF."),
            Length(min=2, max=2, message="UF deve ter 2 letras (ex.: PE)."),
        ],
    )

    situacao = SelectField(
        "Situação",
        choices=[
            ("ATIVA", "Ativa"),
            ("INATIVA", "Inativa"),
            ("MANUTENCAO", "Manutenção"),
        ],
        validators=[DataRequired(message="Selecione uma situação.")],
    )

    descricao_situacao = TextAreaField(
        "Descrição",
        validators=[Length(max=2000), _descricao_situacao_obrigatoria],
    )

    submit = SubmitField("Salvar")


class AlterarSituacaoForm(FlaskForm):
    situacao = SelectField(
        "Nova situação",
        choices=[
            ("ATIVA", "Ativa"),
            ("INATIVA", "Inativa"),
            ("MANUTENCAO", "Manutenção"),
        ],
        validators=[DataRequired(message="Selecione uma situação.")],
    )
    descricao_situacao = TextAreaField(
        "Descrição",
        validators=[Length(max=2000), _descricao_situacao_obrigatoria],
    )
    submit = SubmitField("Alterar situação")


def _coerce_opcional_int(valor):
    if valor in (None, "", "None"):
        return None
    return int(valor)


class ServicoForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome do serviço."), Length(max=150)],
    )

    unidade_id = SelectField(
        "Unidade",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Selecione a unidade.")],
    )

    situacao = SelectField(
        "Situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("MANUTENCAO", "Manutenção")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )

    descricao_situacao = TextAreaField(
        "Descrição",
        validators=[Length(max=2000), _descricao_situacao_obrigatoria],
    )

    submit = SubmitField("Salvar")


class EquipamentoForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome do equipamento."), Length(max=150)],
    )

    tipo = StringField(
        "Tipo",
        validators=[DataRequired(message="Informe o tipo do equipamento."), Length(max=100)],
    )

    unidade_id = SelectField(
        "Unidade",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Selecione a unidade.")],
    )

    servico_id = SelectField(
        "Serviço (opcional)",
        choices=[],
        coerce=_coerce_opcional_int,
        validate_choice=True,
    )

    situacao = SelectField(
        "Situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("MANUTENCAO", "Manutenção")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )

    descricao_situacao = TextAreaField(
        "Descrição",
        validators=[Length(max=2000), _descricao_situacao_obrigatoria],
    )

    submit = SubmitField("Salvar")


class AlterarSituacaoAtivoInativoForm(FlaskForm):
    situacao = SelectField(
        "Nova situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("MANUTENCAO", "Manutenção")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )
    descricao_situacao = TextAreaField(
        "Descrição",
        validators=[Length(max=2000), _descricao_situacao_obrigatoria],
    )
    submit = SubmitField("Alterar situação")


class AcaoAlteracaoForm(FlaskForm):
    motivo_rejeicao = TextAreaField("Descrição", validators=[Length(max=2000)])
    submit = SubmitField("Confirmar")


class CriarUsuarioForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=150)],
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Informe o email."),
            Email(message="Email inválido.", check_deliverability=False),
            Length(max=150),
        ],
    )

    senha = PasswordField(
        "Senha",
        validators=[
            DataRequired(message="Informe a senha."),
            Length(min=8, max=255, message="A senha deve ter no mínimo 8 caracteres."),
        ],
    )

    perfil = SelectField(
        "Perfil",
        choices=[
            ("ADMINISTRADOR", "Administrador"),
            ("GESTAO_INFORMACAO", "Gestão da Informação"),
            ("RESPONSAVEL_SAUDE_BUCAL", "Responsável pela Saúde Bucal"),
            ("GESTOR", "Gestor"),
        ],
        validators=[DataRequired(message="Selecione um perfil.")],
    )

    ativo = SelectField(
        "Situação",
        choices=[("1", "Ativo"), ("0", "Inativo")],
        default="1",
        validators=[DataRequired()],
    )

    submit = SubmitField("Salvar")


class EditarUsuarioForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=150)],
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Informe o email."),
            Email(message="Email inválido.", check_deliverability=False),
            Length(max=150),
        ],
    )

    perfil = SelectField(
        "Perfil",
        choices=[
            ("ADMINISTRADOR", "Administrador"),
            ("GESTAO_INFORMACAO", "Gestão da Informação"),
            ("RESPONSAVEL_SAUDE_BUCAL", "Responsável pela Saúde Bucal"),
            ("GESTOR", "Gestor"),
        ],
        validators=[DataRequired(message="Selecione um perfil.")],
    )

    submit = SubmitField("Salvar")


class RedefinirSenhaForm(FlaskForm):
    nova_senha = PasswordField(
        "Nova senha",
        validators=[
            DataRequired(message="Informe a nova senha."),
            Length(min=8, max=255, message="A senha deve ter no mínimo 8 caracteres."),
        ],
    )
    confirmar_senha = PasswordField(
        "Confirmar nova senha",
        validators=[DataRequired(message="Confirme a nova senha.")],
    )
    submit = SubmitField("Redefinir senha")

    def validate_confirmar_senha(self, field):
        if field.data != self.nova_senha.data:
            raise ValidationError("As senhas informadas não conferem.")


TIPOS_SOLICITACAO_TITULAR = [
    ("ACESSO", "Acesso e confirmação dos meus dados"),
    ("CORRECAO", "Correção de dados incompletos ou desatualizados"),
    ("ELIMINACAO", "Anonimização ou eliminação dos meus dados"),
    ("PORTABILIDADE", "Portabilidade dos meus dados"),
    ("COMPARTILHAMENTO", "Informação sobre com quem meus dados são compartilhados"),
    ("OPOSICAO", "Oposição a um tratamento"),
]


class SolicitacaoTitularForm(FlaskForm):
    tipo = SelectField("Tipo de pedido", choices=TIPOS_SOLICITACAO_TITULAR, validators=[DataRequired()])
    descricao = TextAreaField(
        "Detalhes do pedido",
        validators=[DataRequired(message="Descreva o seu pedido."), Length(max=2000)],
    )
    submit = SubmitField("Enviar pedido")


class RespostaSolicitacaoForm(FlaskForm):
    decisao = SelectField(
        "Decisão",
        choices=[("ATENDIDA", "Atender"), ("NEGADA", "Negar")],
        validators=[DataRequired()],
    )
    resposta = TextAreaField(
        "Resposta ao titular",
        validators=[DataRequired(message="Escreva a resposta ao titular."), Length(max=2000)],
    )
    submit = SubmitField("Registrar resposta")
