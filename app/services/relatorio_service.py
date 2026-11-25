import csv
import io
import re

from app.models import Auditoria, Equipamento, Servico, Unidade
from app.utils.datetime_utils import utcnow

ENTIDADES_RELATORIO = ("unidades", "servicos", "equipamentos")

_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


def sanitizar_celula(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SIM" if valor else "NAO"
    if hasattr(valor, "value"):
        valor = valor.value
    texto = str(valor)
    if texto.startswith(_PERIGOSOS):
        return "'" + texto
    return texto


def _linhas_unidades():
    cabecalho = ["id", "nome", "cnes", "unidade_mista", "tipo", "endereco", "bairro", "cidade", "uf", "situacao"]
    linhas = [
        [u.id, u.nome, u.cnes, u.unidade_e_mista, u.tipo, u.endereco, u.bairro, u.cidade, u.uf, u.situacao]
        for u in Unidade.query.order_by(Unidade.nome).all()
    ]
    return cabecalho, linhas


def _linhas_servicos():
    cabecalho = ["id", "nome", "unidade_id", "unidade", "situacao"]
    linhas = [
        [s.id, s.nome, s.unidade_id, s.unidade.nome if s.unidade else "", s.situacao]
        for s in Servico.query.order_by(Servico.nome).all()
    ]
    return cabecalho, linhas


def _linhas_equipamentos():
    cabecalho = ["id", "nome", "tipo", "unidade_id", "unidade", "servico_id", "servico", "situacao"]
    linhas = [
        [
            e.id, e.nome, e.tipo, e.unidade_id, e.unidade.nome if e.unidade else "",
            e.servico_id, e.servico.nome if e.servico else "", e.situacao,
        ]
        for e in Equipamento.query.order_by(Equipamento.nome).all()
    ]
    return cabecalho, linhas


_GERADORES = {
    "unidades": _linhas_unidades,
    "servicos": _linhas_servicos,
    "equipamentos": _linhas_equipamentos,
}


def gerar_csv(entidade):
    if entidade not in _GERADORES:
        raise ValueError("Entidade de relatório desconhecida.")

    cabecalho, linhas = _GERADORES[entidade]()
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow([sanitizar_celula(c) for c in linha])

    carimbo = utcnow().strftime("%Y%m%d-%H%M%S")
    nome_arquivo = f"oris-{entidade}-{carimbo}.csv"
    return nome_arquivo, ("﻿" + buffer.getvalue()).encode("utf-8")


_PADRAO_EXPORTACAO = re.compile(r"\(objeto (?P<chave>[^)]+)\), SHA-256 (?P<sha>[0-9a-f]{64})")
_PADRAO_EXPORTACAO_DRIVE = re.compile(
    r"via (?P<metodo>OIDC|OAuth2 M2M) \(arquivo (?P<arquivo>[^,]+), destino [^)]+\), SHA-256 (?P<sha>[0-9a-f]{64})"
)
_DESTINOS_DRIVE = {"OIDC": "Google Drive (OIDC)", "OAuth2 M2M": "Google Drive (M2M)"}
CABECALHO_HISTORICO = [
    "data_hora_utc", "relatorio", "exportado_por", "origem_ip", "arquivo", "objeto_s3", "sha256", "destino",
]


def _dados_da_exportacao(registro):
    descricao = registro.descricao or ""
    if registro.acao == "EXPORTAR_DRIVE":
        achado = _PADRAO_EXPORTACAO_DRIVE.search(descricao)
        if not achado:
            return {"destino": "Google Drive", "arquivo": "", "chave": "", "sha256": ""}
        return {
            "destino": _DESTINOS_DRIVE[achado["metodo"]],
            "arquivo": achado["arquivo"],
            "chave": "",
            "sha256": achado["sha"],
        }
    achado = _PADRAO_EXPORTACAO.search(descricao)
    chave = achado["chave"] if achado else ""
    return {
        "destino": "Amazon S3",
        "arquivo": chave.rsplit("/", 1)[-1],
        "chave": chave,
        "sha256": achado["sha"] if achado else "",
    }


def historico_exportacoes(limite=500):
    registros = (
        Auditoria.query.filter(
            Auditoria.acao.in_(("EXPORTAR_RELATORIO", "EXPORTAR_DRIVE")),
            Auditoria.resultado == "SUCESSO",
        )
        .order_by(Auditoria.data_hora.desc(), Auditoria.id.desc())
        .limit(limite)
        .all()
    )
    return [
        {
            "data_hora": r.data_hora,
            "relatorio": r.tabela or "",
            "usuario": r.usuario.nome if r.usuario else "",
            "ip": r.origem_ip or "",
            **_dados_da_exportacao(r),
        }
        for r in registros
    ]


def gerar_csv_historico():
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(CABECALHO_HISTORICO)
    for h in historico_exportacoes(limite=100000):
        escritor.writerow([sanitizar_celula(c) for c in (
            h["data_hora"].strftime("%Y-%m-%d %H:%M:%S"), h["relatorio"], h["usuario"],
            h["ip"], h["arquivo"], h["chave"], h["sha256"], h["destino"],
        )])
    carimbo = utcnow().strftime("%Y%m%d-%H%M%S")
    return f"oris-historico-exportacoes-{carimbo}.csv", ("﻿" + buffer.getvalue()).encode("utf-8")
