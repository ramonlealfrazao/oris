import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        insp = inspect(db.engine)
        comandos = []

        col_unidades = {c["name"] for c in insp.get_columns("unidades")}
        idx_cnes = [i for i in insp.get_indexes("unidades") if i["column_names"] == ["cnes"]]
        uniques = [i for i in idx_cnes if i["unique"]]
        tem_comum = any(not i["unique"] for i in idx_cnes)
        for i in uniques:
            comandos.append(f"ALTER TABLE unidades DROP INDEX {i['name']}")
        if uniques or not idx_cnes:
            if not tem_comum:
                comandos.append("CREATE INDEX ix_unidades_cnes ON unidades (cnes)")
        if "unidade_e_mista" not in col_unidades:
            comandos.append(
                "ALTER TABLE unidades ADD COLUMN unidade_e_mista BOOLEAN NOT NULL DEFAULT FALSE AFTER cnes"
            )
        for tabela in ("servicos", "equipamentos"):
            coluna = next(c for c in insp.get_columns(tabela) if c["name"] == "unidade_id")
            if not coluna["nullable"]:
                comandos.append(f"ALTER TABLE {tabela} MODIFY COLUMN unidade_id INT NULL")

        colunas = {c["name"] for c in insp.get_columns("usuarios")}
        if "origem" not in colunas:
            comandos.append(
                "ALTER TABLE usuarios ADD COLUMN origem "
                "ENUM('LOCAL','LDAP','OIDC') NOT NULL DEFAULT 'LOCAL'"
            )
        if "identificador_externo" not in colunas:
            comandos.append("ALTER TABLE usuarios ADD COLUMN identificador_externo VARCHAR(255) NULL")
            comandos.append("CREATE INDEX ix_usuarios_identificador_externo ON usuarios (identificador_externo)")

        for tabela in ("unidades", "servicos", "equipamentos"):
            colunas_tabela = {c["name"] for c in insp.get_columns(tabela)}
            if "descricao_situacao" not in colunas_tabela:
                comandos.append(f"ALTER TABLE {tabela} ADD COLUMN descricao_situacao TEXT NULL")

        colunas_alteracoes = {c["name"] for c in insp.get_columns("alteracoes")}
        if "motivo_rejeicao" not in colunas_alteracoes:
            comandos.append("ALTER TABLE alteracoes ADD COLUMN motivo_rejeicao TEXT NULL")

        for tabela in ("servicos", "equipamentos"):
            coluna_situacao = next(
                c for c in insp.get_columns(tabela) if c["name"] == "situacao"
            )
            if "MANUTENCAO" not in str(coluna_situacao["type"]).upper():
                comandos.append(
                    f"ALTER TABLE {tabela} MODIFY COLUMN situacao "
                    "ENUM('ATIVO','INATIVO','MANUTENCAO') NOT NULL DEFAULT 'ATIVO'"
                )

        cols_aud = {c["name"]: c for c in insp.get_columns("auditorias")}
        if "origem_ip" not in cols_aud:
            comandos.append("ALTER TABLE auditorias ADD COLUMN origem_ip VARCHAR(45) NULL")
        if "resultado" not in cols_aud:
            comandos.append("ALTER TABLE auditorias ADD COLUMN resultado VARCHAR(10) NOT NULL DEFAULT 'SUCESSO'")
        if "identificador_tentado" not in cols_aud:
            comandos.append("ALTER TABLE auditorias ADD COLUMN identificador_tentado VARCHAR(255) NULL")
        if not cols_aud["usuario_id"]["nullable"]:
            comandos.append("ALTER TABLE auditorias MODIFY COLUMN usuario_id INT NULL")

        cols_usu = {c["name"] for c in insp.get_columns("usuarios")}
        for coluna, ddl in (
            ("mfa_ativo", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("mfa_segredo", "TEXT NULL"),
            ("mfa_ultimo_passo", "BIGINT NULL"),
            ("mfa_codigos_recuperacao", "TEXT NULL"),
        ):
            if coluna not in cols_usu:
                comandos.append(f"ALTER TABLE usuarios ADD COLUMN {coluna} {ddl}")

        for comando in comandos:
            db.session.execute(text(comando))
        db.session.commit()

        if comandos:
            print(f"Banco atualizado ({len(comandos)} alteracao(oes) no banco).")
        else:
            print("Banco ja esta atualizado.")

        from app.bd import objetos

        aplicados, ignorados = objetos.aplicar_objetos()
        print(f"Objetos do MySQL: {aplicados} comando(s) aplicados (views sempre; funcoes/triggers se permitido).")
        if ignorados:
            print("AVISO: o MySQL recusou criar funcoes/procedimentos/triggers (erro 1419: binlog ligado e usuario sem SUPER):")
            print("       " + "; ".join(ignorados))
            print("       O sistema e o dashboard funcionam sem eles. Para habilita-los, como administrador (root), execute UMA vez:")
            print("         SET GLOBAL log_bin_trust_function_creators = 1;")
            print("       e rode este script de novo.")

if __name__ == "__main__":
    main()
