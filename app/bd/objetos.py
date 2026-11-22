import os
import re

from app.bd.conexao import ErroBanco, abrir_conexao, consultar, transacao

ARQUIVO_SQL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "database", "etapa05_objetos.sql",
)

SQL_DEFINIR_USUARIO = "SET @oris_usuario_id = %s"
SQL_LER_NOVA_MANUTENCAO = "SELECT @nova_manutencao AS manutencao_id"
SQL_ROTINAS = (
    "SELECT ROUTINE_NAME AS nome, ROUTINE_TYPE AS tipo FROM information_schema.ROUTINES "
    "WHERE ROUTINE_SCHEMA = DATABASE()"
)
SQL_TRIGGERS = "SELECT TRIGGER_NAME AS nome FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE()"
SQL_VIEWS = "SELECT TABLE_NAME AS nome FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE()"

FUNCOES = {
    "fn_pct_equip_operantes": {
        "titulo": "Percentual de equipamentos operantes",
        "descricao": "Devolve o % de equipamentos ATIVOS de uma unidade (NULL se não tiver equipamentos).",
        "parametros": [{"nome": "unidade_id", "rotulo": "Unidade", "tipo": "unidade"}],
        "sql": "SELECT fn_pct_equip_operantes(%s) AS resultado",
    },
    "fn_classificar_unidade": {
        "titulo": "Classificação da unidade",
        "descricao": "CRITICA (<50%), ATENCAO (<80%), ADEQUADA (>=80%) ou SEM_EQUIPAMENTO. Chama a função anterior.",
        "parametros": [{"nome": "unidade_id", "rotulo": "Unidade", "tipo": "unidade"}],
        "sql": "SELECT fn_classificar_unidade(%s) AS resultado",
    },
    "fn_custo_manutencao": {
        "titulo": "Custo de manutenção da unidade",
        "descricao": "Soma o custo das manutenções CONCLUÍDAS da unidade; informe o ano ou deixe vazio para todos.",
        "parametros": [{"nome": "unidade_id", "rotulo": "Unidade", "tipo": "unidade"},
                       {"nome": "ano", "rotulo": "Ano (opcional)", "tipo": "ano"}],
        "sql": "SELECT fn_custo_manutencao(%s, %s) AS resultado",
    },
}

PROCEDIMENTOS = {
    "sp_abrir_manutencao": {
        "titulo": "Abrir manutenção",
        "descricao": "Valida o equipamento e insere uma manutenção ABERTA. Se for CORRETIVA, o trigger "
                     "trg_manutencoes_ai coloca o equipamento em INATIVO.",
        "parametros": [{"nome": "equipamento_id", "rotulo": "Equipamento", "tipo": "equipamento"},
                       {"nome": "tipo", "rotulo": "Tipo", "tipo": "tipo_manutencao"},
                       {"nome": "descricao", "rotulo": "Descrição", "tipo": "texto"}],
        "escrita": True,
        "sql": "CALL sp_abrir_manutencao(%s, %s, %s, @nova_manutencao)",
    },
    "sp_concluir_manutencao": {
        "titulo": "Concluir manutenção",
        "descricao": "Conclui uma manutenção ABERTA e grava o custo. O trigger trg_manutencoes_au devolve o "
                     "equipamento à operação.",
        "parametros": [{"nome": "manutencao_id", "rotulo": "Manutenção aberta", "tipo": "manutencao_aberta"},
                       {"nome": "custo", "rotulo": "Custo (R$)", "tipo": "custo"}],
        "escrita": True,
        "sql": "CALL sp_concluir_manutencao(%s, %s)",
    },
    "sp_resumo_unidade": {
        "titulo": "Resumo da unidade",
        "descricao": "Devolve um conjunto de resultados com serviços, equipamentos, % operante, "
                     "classificação e custo (usa as 3 funções).",
        "parametros": [{"nome": "unidade_id", "rotulo": "Unidade", "tipo": "unidade"}],
        "escrita": False,
        "sql": "CALL sp_resumo_unidade(%s)",
    },
    "sp_inativar_unidade": {
        "titulo": "Inativar unidade (cascata)",
        "descricao": "Inativa a unidade e seus serviços/equipamentos numa transação; os triggers de "
                     "auditoria registram cada mudança.",
        "parametros": [{"nome": "unidade_id", "rotulo": "Unidade", "tipo": "unidade"}],
        "escrita": True,
        "sql": "CALL sp_inativar_unidade(%s)",
    },
}

TRIGGERS = {
    "trg_manutencoes_bi": "BEFORE INSERT em manutencoes: valida custo e preenche datas padrão.",
    "trg_manutencoes_bu": "BEFORE UPDATE em manutencoes: impede conclusão anterior à abertura e custo negativo.",
    "trg_manutencoes_ai": "AFTER INSERT em manutencoes: corretiva aberta coloca o equipamento em INATIVO.",
    "trg_manutencoes_au": "AFTER UPDATE em manutencoes: ao encerrar a corretiva, o equipamento volta a ATIVO.",
    "trg_equipamentos_au": "AFTER UPDATE em equipamentos: grava em auditorias cada mudança de situação.",
    "trg_unidades_au": "AFTER UPDATE em unidades: grava em auditorias cada mudança de situação.",
    "trg_auditorias_bu": "BEFORE UPDATE em auditorias: barra qualquer alteração (trilha imutável).",
    "trg_auditorias_bd": "BEFORE DELETE em auditorias: barra qualquer exclusão (trilha imutável).",
}

VIEWS = {
    "vw_painel_unidades": "Painel por unidade: equipamentos operantes, classificação, manutenções abertas e custo (autossuficiente).",
    "vw_manutencoes_detalhe": "Manutenções com equipamento, unidade e duração em dias.",
    "vw_resumo_manutencao_mensal": "Manutenções agregadas por mês e tipo (quantidade, custo, duração média).",
}


def ler_comandos(caminho=ARQUIVO_SQL):
    with open(caminho, encoding="utf-8") as arq:
        texto = arq.read()
    comandos = []
    for bloco in re.split(r"\s*\$\$[ \t]*(?:\r?\n|$)", texto):
        conteudo = bloco.strip()
        while conteudo.startswith("--"):
            conteudo = conteudo.split("\n", 1)[1].lstrip() if "\n" in conteudo else ""
        if conteudo:
            comandos.append(conteudo)
    return comandos


def codigo_fonte(nome):
    padrao = rf"CREATE\s+(OR\s+REPLACE\s+)?(FUNCTION|PROCEDURE|TRIGGER|VIEW)\s+{re.escape(nome)}\b"
    for comando in ler_comandos():
        if re.match(padrao, comando, flags=re.IGNORECASE):
            return comando
    return ""


SQL_PODE_CRIAR_FUNCOES_E_TRIGGERS = (
    "SELECT @@global.log_bin = 0 OR @@global.log_bin_trust_function_creators = 1 "
    "OR EXISTS (SELECT 1 FROM information_schema.USER_PRIVILEGES "
    "WHERE PRIVILEGE_TYPE = 'SUPER' AND GRANTEE = CONCAT(\"'\", "
    "SUBSTRING_INDEX(CURRENT_USER(), '@', 1), \"'@'\", SUBSTRING_INDEX(CURRENT_USER(), '@', -1), \"'\"))"
)


def _e_funcao_ou_trigger(sql):
    primeira = " ".join(sql.split()[:3]).upper()
    return any(f"{verbo} {tipo}" in primeira for verbo in ("DROP", "CREATE") for tipo in ("FUNCTION", "TRIGGER"))


def _pode_criar_funcoes_e_triggers(cur):
    try:
        cur.execute(SQL_PODE_CRIAR_FUNCOES_E_TRIGGERS)
        linha = cur.fetchone()
        valor = linha[0] if not isinstance(linha, dict) else next(iter(linha.values()))
        return bool(valor)
    except Exception:
        return True


def aplicar_objetos(conexao=None):
    propria = conexao is None
    conexao = conexao or abrir_conexao()
    aplicados, ignorados = 0, []
    try:
        with conexao.cursor() as cur:
            pode = _pode_criar_funcoes_e_triggers(cur)
            for sql in ler_comandos():
                if not pode and _e_funcao_ou_trigger(sql):
                    primeira = sql.splitlines()[0]
                    if not primeira.upper().startswith("DROP"):
                        ignorados.append(primeira.split("(")[0].strip())
                    continue
                try:
                    cur.execute(sql)
                    aplicados += 1
                except Exception as erro:
                    if getattr(erro, "args", (None,))[0] != 1419:
                        raise
                    primeira = sql.splitlines()[0]
                    if not primeira.upper().startswith("DROP"):
                        ignorados.append(primeira.split("(")[0].strip())
        conexao.commit()
        return aplicados, ignorados
    finally:
        if propria:
            conexao.close()


def _traduzir(erro):
    args = getattr(erro, "args", ())
    if len(args) >= 2:
        return str(args[1])
    return str(erro)


def executar_funcao(nome, valores):
    cfg = FUNCOES.get(nome)
    if cfg is None:
        raise ErroBanco("Função desconhecida.")
    try:
        _, linhas = consultar(cfg["sql"], valores)
    except Exception as erro:
        raise ErroBanco(_traduzir(erro)) from erro
    return linhas[0]["resultado"] if linhas else None


def chamar_procedimento(nome, valores, usuario_id):
    cfg = PROCEDIMENTOS.get(nome)
    if cfg is None:
        raise ErroBanco("Procedimento desconhecido.")
    try:
        with transacao() as cur:
            cur.execute(SQL_DEFINIR_USUARIO, (usuario_id,))
            cur.execute(cfg["sql"], valores)
            if nome == "sp_abrir_manutencao":
                cur.execute(SQL_LER_NOVA_MANUTENCAO)
                return ["manutencao_id"], list(cur.fetchall())
            linhas = list(cur.fetchall() or [])
            colunas = [d[0] for d in (cur.description or [])]
            return colunas, linhas
    except ErroBanco:
        raise
    except Exception as erro:
        raise ErroBanco(_traduzir(erro)) from erro


def objetos_existentes():
    _, rotinas = consultar(SQL_ROTINAS)
    _, triggers = consultar(SQL_TRIGGERS)
    _, views = consultar(SQL_VIEWS)
    return {
        "funcoes": {r["nome"] for r in rotinas if r["tipo"] == "FUNCTION"},
        "procedimentos": {r["nome"] for r in rotinas if r["tipo"] == "PROCEDURE"},
        "triggers": {t["nome"] for t in triggers},
        "views": {v["nome"] for v in views},
    }


SQL_EFEITOS_TRIGGERS = """
    SELECT id, data_hora, acao, tabela, registro_id, descricao, valor_anterior, valor_novo
      FROM auditorias
     WHERE acao LIKE 'TRG\\_%'
     ORDER BY id DESC
     LIMIT 30
"""


def efeitos_triggers():
    _, linhas = consultar(SQL_EFEITOS_TRIGGERS)
    return linhas
