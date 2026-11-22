import json
from datetime import timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Auditoria,
    PerfilUsuario,
    SolicitacaoTitular,
    StatusSolicitacaoTitular,
    TipoSolicitacaoTitular,
    Usuario,
)
from app.services import lgpd_service
from app.utils.datetime_utils import utcnow
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        for perfil, email in EMAILS.items():
            db.session.add(
                Usuario(
                    nome=f"Usuário {perfil.value}",
                    email=email,
                    senha_hash=gerar_hash_senha(SENHA),
                    perfil=perfil,
                    ativo=True,
                )
            )
        db.session.add(
            Usuario(
                nome="Segundo Admin",
                email="admin2@oris.com.br",
                senha_hash=gerar_hash_senha(SENHA),
                perfil=PerfilUsuario.ADMINISTRADOR,
                ativo=True,
            )
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def entrar(client, email):
    return client.post("/login", data={"email": email, "senha": SENHA})


def usuario(email):
    return Usuario.query.filter_by(email=email).one()


def acoes():
    return [a.acao for a in Auditoria.query.all()]


def test_meus_dados_exige_login(client):
    resp = client.get("/lgpd/meus-dados")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


@pytest.mark.parametrize("perfil", list(PerfilUsuario))
def test_todo_perfil_ve_os_proprios_dados(client, perfil):
    entrar(client, EMAILS[perfil])
    resp = client.get("/lgpd/meus-dados")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert EMAILS[perfil] in html
    for outro in EMAILS.values():
        if outro != EMAILS[perfil]:
            assert outro not in html


def test_exportacao_traz_dados_sem_senha_e_audita(client, app):
    entrar(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.post("/lgpd/meus-dados/exportar")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["Content-Disposition"]
    assert resp.headers["Cache-Control"] == "no-store"
    corpo = json.loads(resp.get_data(as_text=True))
    cadastro = corpo["titular"]["cadastro"]
    assert cadastro["email"] == EMAILS[PerfilUsuario.GESTOR]
    texto = resp.get_data(as_text=True)
    assert "senha" not in texto.lower()
    with app.app_context():
        assert "LGPD_EXPORTACAO" in acoes()
        assert usuario(EMAILS[PerfilUsuario.GESTOR]).senha_hash not in texto


def test_exportacao_exige_login(client):
    assert client.post("/lgpd/meus-dados/exportar").status_code == 302


def test_nova_solicitacao_grava_prazo_e_audita(client, app):
    entrar(client, EMAILS[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
    resp = client.post("/lgpd/solicitacoes/nova", data={"tipo": "CORRECAO", "descricao": "Meu nome está errado"})
    assert resp.status_code == 302
    with app.app_context():
        s = SolicitacaoTitular.query.one()
        assert s.tipo == TipoSolicitacaoTitular.CORRECAO
        assert s.status == StatusSolicitacaoTitular.ABERTA
        assert timedelta(days=14) < s.prazo_resposta - s.criada_em <= timedelta(days=15, seconds=1)
        assert "LGPD_SOLICITACAO" in acoes()


def test_solicitacao_sem_descricao_nao_e_gravada(client, app):
    entrar(client, EMAILS[PerfilUsuario.GESTOR])
    client.post("/lgpd/solicitacoes/nova", data={"tipo": "ACESSO", "descricao": ""})
    with app.app_context():
        assert SolicitacaoTitular.query.count() == 0


def test_tipo_invalido_e_recusado(client, app):
    entrar(client, EMAILS[PerfilUsuario.GESTOR])
    client.post("/lgpd/solicitacoes/nova", data={"tipo": "QUALQUER", "descricao": "x"})
    with app.app_context():
        assert SolicitacaoTitular.query.count() == 0


def criar_solicitacao(app, email, tipo="ACESSO"):
    with app.app_context():
        s = lgpd_service.registrar_solicitacao(usuario(email), tipo, "pedido de teste")
        return s.id


@pytest.mark.parametrize(
    "perfil",
    [PerfilUsuario.GESTAO_INFORMACAO, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL, PerfilUsuario.GESTOR],
)
def test_so_administrador_trata_pedidos(client, app, perfil):
    sid = criar_solicitacao(app, EMAILS[PerfilUsuario.GESTOR])
    entrar(client, EMAILS[perfil])
    assert client.get("/lgpd/solicitacoes").status_code == 403
    assert client.get(f"/lgpd/solicitacoes/{sid}").status_code == 403
    assert client.post(f"/lgpd/solicitacoes/{sid}", data={"decisao": "ATENDIDA", "resposta": "ok"}).status_code == 403
    assert client.post(f"/lgpd/solicitacoes/{sid}/anonimizar").status_code == 403


def test_administrador_responde_pedido(client, app):
    sid = criar_solicitacao(app, EMAILS[PerfilUsuario.GESTOR])
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    assert client.get("/lgpd/solicitacoes").status_code == 200
    resp = client.post(f"/lgpd/solicitacoes/{sid}", data={"decisao": "ATENDIDA", "resposta": "Dados enviados."})
    assert resp.status_code == 302
    with app.app_context():
        s = db.session.get(SolicitacaoTitular, sid)
        assert s.status == StatusSolicitacaoTitular.ATENDIDA
        assert s.resposta == "Dados enviados."
        assert s.respondida_por == usuario(EMAILS[PerfilUsuario.ADMINISTRADOR]).id
        assert "LGPD_RESPOSTA" in acoes()


def test_pedido_respondido_nao_muda_de_novo(client, app):
    sid = criar_solicitacao(app, EMAILS[PerfilUsuario.GESTOR])
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    client.post(f"/lgpd/solicitacoes/{sid}", data={"decisao": "NEGADA", "resposta": "Sem base."})
    client.post(f"/lgpd/solicitacoes/{sid}", data={"decisao": "ATENDIDA", "resposta": "Mudei de ideia."})
    with app.app_context():
        s = db.session.get(SolicitacaoTitular, sid)
        assert s.status == StatusSolicitacaoTitular.NEGADA
        assert s.resposta == "Sem base."


def test_resposta_vazia_e_recusada(client, app):
    sid = criar_solicitacao(app, EMAILS[PerfilUsuario.GESTOR])
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    client.post(f"/lgpd/solicitacoes/{sid}", data={"decisao": "ATENDIDA", "resposta": ""})
    with app.app_context():
        assert db.session.get(SolicitacaoTitular, sid).status == StatusSolicitacaoTitular.ABERTA


def test_pedido_inexistente_da_404(client):
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    assert client.get("/lgpd/solicitacoes/999").status_code == 404


def test_anonimizacao_remove_dados_pessoais_e_mantem_a_trilha(client, app):
    email = EMAILS[PerfilUsuario.GESTOR]
    sid = criar_solicitacao(app, email, "ELIMINACAO")
    with app.app_context():
        uid = usuario(email).id
        total_antes = Auditoria.query.filter_by(usuario_id=uid).count()
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    resp = client.post(f"/lgpd/solicitacoes/{sid}/anonimizar")
    assert resp.status_code == 302
    with app.app_context():
        u = db.session.get(Usuario, uid)
        assert u.ativo is False
        assert email not in u.email and u.nome.startswith("Usuário anonimizado")
        assert u.identificador_externo is None
        assert Auditoria.query.filter_by(usuario_id=uid).count() >= total_antes
        assert "LGPD_ANONIMIZACAO" in acoes()
    novo = client.application.test_client()
    resp = novo.post("/login", data={"email": email, "senha": SENHA}, follow_redirects=True)
    assert "Dashboard" not in resp.get_data(as_text=True)


def test_anonimizacao_so_vale_para_pedido_de_eliminacao(client, app):
    sid = criar_solicitacao(app, EMAILS[PerfilUsuario.GESTOR], "ACESSO")
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    assert client.post(f"/lgpd/solicitacoes/{sid}/anonimizar").status_code == 400
    with app.app_context():
        assert usuario(EMAILS[PerfilUsuario.GESTOR]).ativo is True


def test_ultimo_administrador_nao_e_anonimizado(client, app):
    with app.app_context():
        db.session.delete(usuario("admin2@oris.com.br"))
        db.session.commit()
    sid = criar_solicitacao(app, EMAILS[PerfilUsuario.ADMINISTRADOR], "ELIMINACAO")
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    client.post(f"/lgpd/solicitacoes/{sid}/anonimizar")
    with app.app_context():
        assert usuario(EMAILS[PerfilUsuario.ADMINISTRADOR]).ativo is True


def test_pedido_vencido_aparece_no_resumo(app):
    with app.app_context():
        s = lgpd_service.registrar_solicitacao(usuario(EMAILS[PerfilUsuario.GESTOR]), "ACESSO", "teste")
        s.prazo_resposta = utcnow() - timedelta(days=1)
        db.session.commit()
        resumo = lgpd_service.resumo_conformidade()
        assert resumo["solicitacoes_abertas"] == 1
        assert resumo["solicitacoes_vencidas"] == 1


def test_privacidade_publica_traz_controlador_e_direitos(client):
    resp = client.get("/privacidade")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Finalidade" in html
    assert "Secretaria de Saúde do Recife" in html
    assert "Seus direitos" in html
    assert "Base legal" in html
    assert "[definir pelo órgão responsável]" not in html
    assert "ainda não designado" in html


def test_privacidade_mostra_encarregado_configurado(app, client):
    app.config["LGPD_ENCARREGADO_NOME"] = "Maria Silva"
    app.config["LGPD_ENCARREGADO_EMAIL"] = "dpo@exemplo.gov.br"
    html = client.get("/privacidade").get_data(as_text=True)
    assert "Maria Silva" in html
    assert "dpo@exemplo.gov.br" in html
    assert "ainda não designado" not in html


def test_retencao_configuravel_aparece_na_pagina(app, client):
    app.config["LGPD_RETENCAO_AUDITORIA_ANOS"] = 5
    html = client.get("/privacidade").get_data(as_text=True)
    assert "5 ano(s)" in html


def test_anonimizacao_apaga_tambem_o_mfa(client, app):
    email = EMAILS[PerfilUsuario.GESTOR]
    sid = criar_solicitacao(app, email, "ELIMINACAO")
    with app.app_context():
        u = usuario(email)
        u.mfa_ativo, u.mfa_segredo = True, "oris-fernet-v1:segredo-cifrado"
        u.mfa_ultimo_passo, u.mfa_codigos_recuperacao = 123, '["hash"]'
        db.session.commit()
        uid = u.id
    entrar(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    assert client.post(f"/lgpd/solicitacoes/{sid}/anonimizar").status_code == 302
    with app.app_context():
        u = db.session.get(Usuario, uid)
        assert u.mfa_ativo is False and u.mfa_segredo is None
        assert u.mfa_ultimo_passo is None and u.mfa_codigos_recuperacao is None


def test_meus_dados_informa_mfa_sem_expor_o_segredo(app):
    with app.app_context():
        u = usuario(EMAILS[PerfilUsuario.GESTOR])
        u.mfa_ativo, u.mfa_segredo = True, "oris-fernet-v1:segredo-cifrado"
        db.session.commit()
        dados = lgpd_service.dados_do_titular(u)
    assert dados["cadastro"]["mfa_ativo"] is True
    assert "segredo-cifrado" not in json.dumps(dados)
