import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Alteracao,
    Equipamento,
    PerfilUsuario,
    SituacaoAtivoInativo,
    StatusAlteracao,
    TipoOperacaoAlteracao,
    Unidade,
    Usuario,
)
from app.services import governanca_dados as dados
from app.services import governanca_service as servico
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}

SECOES = ["riscos", "raci", "cobit", "auditoria", "etica", "nuvem"]


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
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def entrar(client, perfil):
    client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA})


@pytest.mark.parametrize("rota", ["/governanca"] + [f"/governanca/{s}" for s in SECOES])
def test_governanca_exige_login(client, rota):
    resp = client.get(rota)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


@pytest.mark.parametrize("perfil", list(PerfilUsuario))
@pytest.mark.parametrize("rota", ["/governanca"] + [f"/governanca/{s}" for s in SECOES])
def test_todo_perfil_abre_todas_as_paginas(client, perfil, rota):
    entrar(client, perfil)
    assert client.get(rota).status_code == 200


def test_secao_inexistente_da_404(client):
    entrar(client, PerfilUsuario.GESTOR)
    assert client.get("/governanca/inexistente").status_code == 404


def test_pagina_inicial_mostra_os_seis_principios(client):
    entrar(client, PerfilUsuario.GESTOR)
    html = client.get("/governanca").get_data(as_text=True)
    for nome in ["Responsabilidade", "Estratégia", "Aquisição", "Desempenho", "Conformidade", "Comportamento humano"]:
        assert nome in html


@pytest.mark.parametrize(
    "p,i,esperado",
    [(1, 1, "baixo"), (1, 5, "baixo"), (2, 3, "medio"), (3, 4, "medio"), (5, 2, "medio"), (3, 5, "alto"), (4, 4, "alto")],
)
def test_nivel_do_risco(p, i, esperado):
    assert servico.nivel_risco(p, i)[1] == esperado


def test_mapa_de_calor_coloca_cada_risco_uma_vez():
    ids = [rid for linha in servico.mapa_de_calor() for c in linha["celulas"] for rid in c["ids"]]
    assert sorted(ids) == sorted(r["id"] for r in dados.RISCOS)
    linha_impacto_4 = next(linha for linha in servico.mapa_de_calor() if linha["impacto"] == 4)
    assert "R1" in linha_impacto_4["celulas"][3]["ids"]


def test_todo_risco_tem_plano_de_mitigacao():
    assert {m["risco"] for m in dados.MITIGACAO} == {r["id"] for r in dados.RISCOS}


def test_riscos_ordenados_do_maior_para_o_menor():
    niveis = [r["nivel"] for r in servico.riscos_com_nivel()]
    assert niveis == sorted(niveis, reverse=True)


def test_raci_tem_um_unico_responsavel_pela_prestacao_de_contas():
    for processo, celulas in dados.RACI:
        assert len(celulas) == len(dados.RACI_COLUNAS)
        assert sum(1 for c in celulas if c.startswith("A")) == 1, processo


def test_indicadores_cobrem_todos_os_principios(app):
    with app.app_context():
        assert set(servico.indicadores()) == {p["chave"] for p in dados.PRINCIPIOS}


def test_indicadores_refletem_os_dados(app):
    with app.app_context():
        unidade = Unidade(nome="U1", cnes="1234567")
        db.session.add(unidade)
        db.session.flush()
        db.session.add_all(
            [
                Equipamento(nome="E1", unidade_id=unidade.id, situacao=SituacaoAtivoInativo.ATIVO),
                Equipamento(nome="E2", unidade_id=unidade.id, situacao=SituacaoAtivoInativo.INATIVO),
                Equipamento(nome="E3", unidade_id=unidade.id, situacao=SituacaoAtivoInativo.INATIVO),
            ]
        )
        admin = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.ADMINISTRADOR]).one()
        for status in (StatusAlteracao.APROVADO, StatusAlteracao.REJEITADO, StatusAlteracao.REJEITADO):
            db.session.add(
                Alteracao(usuario_id=admin.id, tabela="unidades", operacao=TipoOperacaoAlteracao.CRIAR, status=status)
            )
        db.session.commit()

        ind = servico.indicadores()
        desempenho = dict(ind["desempenho"])
        assert desempenho["Equipamentos operantes"] == "33,3%"
        assert desempenho["Unidades em estado crítico"] == 1
        assert dict(ind["responsabilidade"])["Usuários ativos"] == 4
        assert dict(ind["comportamento"])["Taxa de rejeição"] == "66,7%"


def test_indicadores_sem_dados_nao_quebram(app):
    with app.app_context():
        ind = servico.indicadores()
        assert dict(ind["desempenho"])["Equipamentos operantes"] == "sem dados"
        assert dict(ind["comportamento"])["Taxa de rejeição"] == "sem dados"


def test_atalhos_da_trilha_so_para_quem_consulta_auditoria(client):
    entrar(client, PerfilUsuario.GESTOR)
    html = client.get("/governanca/auditoria").get_data(as_text=True)
    assert "Atalhos para a trilha" not in html
    client.get("/logout")
    entrar(client, PerfilUsuario.GESTAO_INFORMACAO)
    html = client.get("/governanca/auditoria").get_data(as_text=True)
    assert "Atalhos para a trilha" in html
    assert "/lgpd/solicitacoes" not in html


def test_menu_tem_governanca_e_meus_dados(client):
    entrar(client, PerfilUsuario.GESTOR)
    html = client.get("/governanca").get_data(as_text=True)
    assert "Governança" in html and "Meus dados" in html
    assert 'href="/lgpd/solicitacoes"' not in html
    client.get("/logout")
    entrar(client, PerfilUsuario.ADMINISTRADOR)
    assert 'href="/lgpd/solicitacoes"' in client.get("/governanca").get_data(as_text=True)
