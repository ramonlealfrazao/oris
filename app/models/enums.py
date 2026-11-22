import enum


class PerfilUsuario(str, enum.Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    GESTAO_INFORMACAO = "GESTAO_INFORMACAO"
    RESPONSAVEL_SAUDE_BUCAL = "RESPONSAVEL_SAUDE_BUCAL"
    GESTOR = "GESTOR"


class OrigemDiretorio(str, enum.Enum):
    LOCAL = "LOCAL"
    LDAP = "LDAP"
    OIDC = "OIDC"


class SituacaoUnidade(str, enum.Enum):
    ATIVA = "ATIVA"
    INATIVA = "INATIVA"
    MANUTENCAO = "MANUTENCAO"


class SituacaoAtivoInativo(str, enum.Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    MANUTENCAO = "MANUTENCAO"


class StatusAlteracao(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class TipoOperacaoAlteracao(str, enum.Enum):
    CRIAR = "CRIAR"
    EDITAR = "EDITAR"
    ALTERAR_SITUACAO = "ALTERAR_SITUACAO"


class TipoSolicitacaoTitular(str, enum.Enum):
    ACESSO = "ACESSO"
    CORRECAO = "CORRECAO"
    ELIMINACAO = "ELIMINACAO"
    PORTABILIDADE = "PORTABILIDADE"
    COMPARTILHAMENTO = "COMPARTILHAMENTO"
    OPOSICAO = "OPOSICAO"


class StatusSolicitacaoTitular(str, enum.Enum):
    ABERTA = "ABERTA"
    ATENDIDA = "ATENDIDA"
    NEGADA = "NEGADA"
