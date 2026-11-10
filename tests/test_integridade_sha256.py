"""Integridade com SHA-256 (requisito de checksum em importação e exportação).

- utilitário `app/utils/integridade.py` (vetores conhecidos do SHA-256);
- download de relatório: cabeçalho X-Content-SHA256 para o destinatário conferir;
- exportação ao S3: o S3 recebe ChecksumSHA256 e RECUSA o objeto se o conteúdo
  chegar corrompido (verificação feita pelo provedor), além de metadado e auditoria;
- importação: o hash do arquivo processado fica registrado na auditoria.
"""

import base64
import hashlib

import pytest

from app.models import Auditoria, PerfilUsuario
from app.utils.integridade import sha256_arquivo, sha256_base64, sha256_hex

# Importa as fixtures e helpers dos testes da Fase 14 (sem duplicar a montagem do app).
from tests.test_fase14_diretorio_relatorios import (  # noqa: F401
    ClienteS3Falso,
    _dados_rede,
    _login,
    app,
    client,
    s3,
)

SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_hex_bate_com_vetor_conhecido():
    assert sha256_hex(b"abc") == SHA256_ABC
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_base64_e_o_digest_em_base64():
    assert sha256_base64(b"abc") == base64.b64encode(bytes.fromhex(SHA256_ABC)).decode()


def test_sha256_arquivo_le_em_blocos_e_bate_com_o_conteudo(tmp_path):
    dados = b"x" * (3 * 1024 * 1024 + 17)  # maior que um bloco de leitura
    caminho = tmp_path / "grande.bin"
    caminho.write_bytes(dados)
    assert sha256_arquivo(str(caminho)) == hashlib.sha256(dados).hexdigest()


def test_download_traz_sha256_no_cabecalho_e_na_auditoria(app, client):
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/relatorios/unidades/baixar")
    esperado = hashlib.sha256(resp.get_data()).hexdigest()
    assert resp.headers["X-Content-SHA256"] == esperado
    with app.app_context():
        registro = Auditoria.query.filter_by(acao="BAIXAR_RELATORIO", tabela="unidades").one()
        assert esperado in registro.descricao


def test_exportacao_s3_envia_checksum_que_o_s3_valida(app, client, s3):
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    client.post("/relatorios/unidades/exportar-s3", follow_redirects=True)

    objeto = next(iter(s3.objetos.values()))
    corpo = objeto["Body"]
    assert objeto["ChecksumAlgorithm"] == "SHA256"
    assert objeto["ChecksumSHA256"] == sha256_base64(corpo)
    assert objeto["Metadata"]["sha256"] == sha256_hex(corpo)
    with app.app_context():
        registro = Auditoria.query.filter_by(acao="EXPORTAR_RELATORIO", tabela="unidades").one()
        assert sha256_hex(corpo) in registro.descricao


def test_importacao_registra_sha256_do_arquivo_na_auditoria(app, client):
    from tests.test_fase10_importacao import (
        CABECALHO_UNIDADES,
        MAPA_UNIDADES,
        _csv_bytes,
        _fluxo_completo_unidade_valida,
    )

    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_UNIDADES, ["UBS Hash", "1112299", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)
    client.post("/importacao/confirmar",
                data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES})

    esperado = hashlib.sha256(_csv_bytes(linhas)).hexdigest()
    with app.app_context():
        registro = Auditoria.query.filter_by(acao="IMPORTAR_PLANILHA", tabela="unidades").one()
        assert esperado in registro.descricao
