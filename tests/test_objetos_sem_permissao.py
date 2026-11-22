"""Sem permissao para criar funcoes/triggers (erro 1419), a migracao NAO pode apagar os existentes."""

from app.bd import objetos


class CursorFalso:
    def __init__(self, pode):
        self.pode = pode
        self.executados = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, *a):
        self.executados.append(sql)

    def fetchone(self):
        return (1 if self.pode else 0,)


class ConexaoFalsa:
    def __init__(self, pode):
        self.cur = CursorFalso(pode)

    def cursor(self):
        return self.cur

    def commit(self):
        pass


def _ddl(cur):
    return [s for s in cur.executados if s is not objetos.SQL_PODE_CRIAR_FUNCOES_E_TRIGGERS]


def test_sem_permissao_nao_apaga_funcoes_nem_triggers():
    con = ConexaoFalsa(pode=False)
    aplicados, ignorados = objetos.aplicar_objetos(con)
    executados = _ddl(con.cur)
    assert not any(objetos._e_funcao_ou_trigger(s) for s in executados)  # nenhum DROP/CREATE deles
    assert any("PROCEDURE" in s.split("(")[0].upper() for s in executados)  # procedures seguem
    assert any("VIEW" in s.split("(")[0].upper() for s in executados)  # views seguem
    assert len(ignorados) == 3 + 8  # 3 funcoes e 8 triggers informados ao usuario


def test_com_permissao_recria_tudo():
    con = ConexaoFalsa(pode=True)
    aplicados, ignorados = objetos.aplicar_objetos(con)
    assert ignorados == []
    assert sum(1 for s in _ddl(con.cur) if s.lstrip().upper().startswith("CREATE TRIGGER")) == 8
