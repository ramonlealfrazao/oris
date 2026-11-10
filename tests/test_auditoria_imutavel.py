"""Auditoria imutável (append-only) imposta pelo banco.

Requisito: o log não pode ser editado nem apagado, e isso precisa valer no
MySQL e não só pela ausência de rota na aplicação. Os triggers
trg_auditorias_bu / trg_auditorias_bd (database/etapa05_objetos.sql) barram
UPDATE e DELETE com SIGNAL; INSERT e SELECT continuam livres.

- Testes estáticos: sempre rodam (sem MySQL).
- Testes contra o MySQL real: defina ORIS_TEST_MYSQL=1 (usam o .env e fazem
  ROLLBACK, então não deixam linhas na trilha).
"""

import os
import pathlib
import re

import pytest

from app import create_app
from app.bd import objetos
from config import DevelopmentConfig

RAIZ = pathlib.Path(__file__).resolve().parent.parent
NOMES = ("trg_auditorias_bu", "trg_auditorias_bd")


def test_catalogo_de_triggers_lista_os_triggers_da_auditoria():
    for nome in NOMES:
        assert nome in objetos.TRIGGERS, nome


@pytest.mark.parametrize("nome,evento", [("trg_auditorias_bu", "UPDATE"), ("trg_auditorias_bd", "DELETE")])
def test_script_sql_define_trigger_que_barra_o_evento(nome, evento):
    codigo = objetos.codigo_fonte(nome)
    assert codigo, f"{nome} não está em database/etapa05_objetos.sql"
    assert re.search(rf"BEFORE\s+{evento}\s+ON\s+auditorias", codigo, re.IGNORECASE)
    assert "SIGNAL SQLSTATE '45000'" in codigo
    assert "imutavel" in codigo


def test_nenhum_codigo_da_aplicacao_altera_ou_apaga_auditorias():
    """Guarda: se alguém passar a fazer UPDATE/DELETE/TRUNCATE em auditorias, o teste falha."""
    padrao = re.compile(
        r"(UPDATE\s+auditorias|DELETE\s+FROM\s+auditorias|TRUNCATE\s+(TABLE\s+)?auditorias"
        r"|Auditoria\.query\.(delete|update))",
        re.IGNORECASE,
    )
    arquivos = [*RAIZ.glob("app/**/*.py"), *RAIZ.glob("scripts/**/*.py"), *RAIZ.glob("database/*.py"),
                *RAIZ.glob("database/*.sql"), RAIZ / "run.py"]
    assert arquivos
    achados = [str(a.relative_to(RAIZ)) for a in arquivos if padrao.search(a.read_text(encoding="utf-8"))]
    assert achados == []


mysql = pytest.mark.skipif(os.getenv("ORIS_TEST_MYSQL") != "1",
                           reason="defina ORIS_TEST_MYSQL=1 para testar contra o MySQL")


class MySQLConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATE_LIMIT_LOGIN_ENABLED = False


@pytest.fixture
def conexao():
    app = create_app(MySQLConfig)
    with app.app_context():
        from app.bd.conexao import abrir_conexao

        aplicados, ignorados = objetos.aplicar_objetos()
        if any("trg_auditorias" in i for i in ignorados):
            pytest.skip("MySQL recusou criar triggers (erro 1419); veja o aviso do aplicar_migracoes.py")
        conn = abrir_conexao()
        try:
            yield conn
        finally:
            conn.rollback()  # nada do teste fica na trilha
            conn.close()


def _inserir(cur):
    cur.execute("SELECT MIN(id) AS id FROM usuarios")
    usuario_id = cur.fetchone()["id"]
    assert usuario_id, "precisa de ao menos um usuário no banco (rode o seed)"
    cur.execute(
        "INSERT INTO auditorias (usuario_id, acao, descricao, data_hora) "
        "VALUES (%s, 'TESTE_IMUTAVEL', 'teste pytest (sofre rollback)', UTC_TIMESTAMP())",
        (usuario_id,),
    )
    return cur.lastrowid


@mysql
def test_insert_continua_permitido(conexao):
    with conexao.cursor() as cur:
        assert _inserir(cur) > 0


@mysql
def test_update_e_barrado_pelo_banco(conexao):
    import pymysql

    with conexao.cursor() as cur:
        registro = _inserir(cur)
        with pytest.raises(pymysql.err.OperationalError) as erro:
            cur.execute("UPDATE auditorias SET descricao = 'adulterado' WHERE id = %s", (registro,))
        assert erro.value.args[0] == 1644 and "imutavel" in erro.value.args[1]


@mysql
def test_delete_e_barrado_pelo_banco(conexao):
    import pymysql

    with conexao.cursor() as cur:
        registro = _inserir(cur)
        with pytest.raises(pymysql.err.OperationalError) as erro:
            cur.execute("DELETE FROM auditorias WHERE id = %s", (registro,))
        assert erro.value.args[0] == 1644 and "imutavel" in erro.value.args[1]
        cur.execute("SELECT COUNT(*) AS n FROM auditorias WHERE id = %s", (registro,))
        assert cur.fetchone()["n"] == 1


@mysql
def test_triggers_de_situacao_continuam_gravando_na_trilha(conexao):
    """Os triggers existentes (AFTER UPDATE em unidades) fazem INSERT em auditorias e não podem quebrar."""
    with conexao.cursor() as cur:
        cur.execute("SELECT id, situacao FROM unidades ORDER BY id LIMIT 1")
        unidade = cur.fetchone()
        if unidade is None:
            pytest.skip("sem unidades no banco")
        nova = "INATIVA" if unidade["situacao"] != "INATIVA" else "ATIVA"
        cur.execute("SELECT COUNT(*) AS n FROM auditorias WHERE acao = 'TRG_UNIDADE_SITUACAO'")
        antes = cur.fetchone()["n"]
        cur.execute("UPDATE unidades SET situacao = %s WHERE id = %s", (nova, unidade["id"]))
        cur.execute("SELECT COUNT(*) AS n FROM auditorias WHERE acao = 'TRG_UNIDADE_SITUACAO'")
        assert cur.fetchone()["n"] == antes + 1


@mysql
def test_trigger_de_situacao_grava_a_origem_ip(conexao):
    """A origem (IP) informada na sessao chega a trilha gravada pelo trigger."""
    with conexao.cursor() as cur:
        cur.execute("SELECT id, situacao FROM unidades ORDER BY id LIMIT 1")
        unidade = cur.fetchone()
        if unidade is None:
            pytest.skip("sem unidades no banco")
        nova = "INATIVA" if unidade["situacao"] != "INATIVA" else "ATIVA"
        cur.execute("SET @oris_origem_ip = %s", ("198.51.100.99",))
        cur.execute("UPDATE unidades SET situacao = %s WHERE id = %s", (nova, unidade["id"]))
        cur.execute("SELECT origem_ip, resultado FROM auditorias WHERE acao = 'TRG_UNIDADE_SITUACAO' "
                    "ORDER BY id DESC LIMIT 1")
        linha = cur.fetchone()
        assert linha["origem_ip"] == "198.51.100.99"
        assert linha["resultado"] == "SUCESSO"
