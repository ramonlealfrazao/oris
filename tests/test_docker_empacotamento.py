"""Guardas do empacotamento Docker e do cookie de sessao em producao (sem precisar do Docker)."""

import importlib
import re
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent


def _carregar_config(monkeypatch, valor):
    import config

    if valor is None:
        monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    else:
        monkeypatch.setenv("SESSION_COOKIE_SECURE", valor)
    return importlib.reload(config)


def test_cookie_secure_e_padrao_em_producao(monkeypatch):
    assert _carregar_config(monkeypatch, None).ProductionConfig.SESSION_COOKIE_SECURE is True
    assert _carregar_config(monkeypatch, "true").ProductionConfig.SESSION_COOKIE_SECURE is True
    assert _carregar_config(monkeypatch, "qualquer").ProductionConfig.SESSION_COOKIE_SECURE is True


def test_cookie_secure_so_desliga_com_false_explicito(monkeypatch):
    assert _carregar_config(monkeypatch, "false").ProductionConfig.SESSION_COOKIE_SECURE is False
    _carregar_config(monkeypatch, None)  # restaura o padrao para os demais testes


def test_compose_nao_expoe_o_banco_e_usa_mysql_8():
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    bloco_db = texto.split("  app:")[0]
    assert re.search(r"image:\s*mysql:8", bloco_db)
    assert "--log-bin-trust-function-creators=1" in bloco_db
    assert "ports:" not in bloco_db, "o banco nao deve ser publicado no computador"
    assert "FLASK_ENV: production" in texto
    assert '"127.0.0.1:${ORIS_PORT:-5000}:5000"' in texto


def test_dockerfile_nao_roda_como_root_e_dockerignore_protege_segredos():
    dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^USER\s+(?!root)\S+", dockerfile, re.MULTILINE)
    ignorados = (RAIZ / ".dockerignore").read_text(encoding="utf-8").split()
    assert ".env" in ignorados and ".git" in ignorados


def test_senhas_do_compose_sao_sobrescreviveis_por_variavel():
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    senhas = re.findall(r"PASSWORD:\s*(\S+)", texto)
    assert senhas and all(x.startswith("${") for x in senhas)


def test_aws_compose_nao_tem_segredo_padrao_e_so_o_caddy_publica_portas():
    texto = (RAIZ / "docker-compose.aws.yml").read_text(encoding="utf-8")
    for var in ("DB_PASSWORD", "DB_ROOT_PASSWORD", "SECRET_KEY", "DATA_ENCRYPTION_KEY", "ORIS_DEMO_SENHA", "ORIS_DOMAIN"):
        assert f"${{{var}:?" in texto, f"{var} deve ser obrigatoria (sem valor padrao)"
    assert 'SESSION_COOKIE_SECURE: "true"' in texto
    app_bloco = texto.split("  app:")[1].split("  caddy:")[0]
    db_bloco = texto.split("  db:")[1].split("  app:")[0]
    assert "ports:" not in app_bloco and "ports:" not in db_bloco
    assert '"443:443"' in texto


def test_caddyfile_tem_hsts():
    assert "Strict-Transport-Security" in (RAIZ / "docker" / "Caddyfile").read_text(encoding="utf-8")


def _app_com_proxies(n):
    from app import create_app
    from config import TestingConfig

    class Cfg(TestingConfig):
        TRUSTED_PROXY_COUNT = n

    app = create_app(Cfg)

    @app.route("/_ip")
    def _ip():
        from flask import request

        return request.remote_addr

    return app


def test_proxyfix_so_confia_no_cabecalho_com_proxy_confiavel_configurado():
    cab = {"X-Forwarded-For": "198.51.100.77"}
    sem = _app_com_proxies(0).test_client().get("/_ip", headers=cab, environ_overrides={"REMOTE_ADDR": "10.0.0.5"})
    com = _app_com_proxies(1).test_client().get("/_ip", headers=cab, environ_overrides={"REMOTE_ADDR": "10.0.0.5"})
    assert sem.get_data(as_text=True) == "10.0.0.5"      # cabecalho forjavel e ignorado
    assert com.get_data(as_text=True) == "198.51.100.77"  # proxy confiavel: IP real do usuario


def test_idp_compose_sem_segredo_padrao_e_sem_portas_publicas():
    texto = (RAIZ / "docker-compose.idp.yml").read_text(encoding="utf-8")
    for var in ("LDAP_ADMIN_PASSWORD", "KC_ADMIN_PASSWORD", "OIDC_CLIENT_SECRET", "ORIS_DOMAIN"):
        assert f"${{{var}:?" in texto, f"{var} deve ser obrigatoria"
    ldap = texto.split("  ldap:")[1].split("  keycloak:")[0]
    keycloak = texto.split("  keycloak:")[1].split("  caddy:")[0]
    assert "ports:" not in ldap and "ports:" not in keycloak
    assert "LDAP_USE_STARTTLS: \"true\"" in texto and "LDAP_ALLOW_INSECURE" not in texto
    assert "OIDC_ISSUER: https://" in texto


def test_caddy_idp_bloqueia_console_admin_do_keycloak():
    texto = (RAIZ / "docker" / "Caddyfile.idp").read_text(encoding="utf-8")
    assert "/admin*" in texto and "respond @admin 403" in texto


def test_realm_gerado_troca_marcadores_e_nao_vaza_segredo_no_modelo(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys

    modelo = (RAIZ / "docker" / "keycloak" / "oris-realm.template.json").read_text(encoding="utf-8")
    json.loads(modelo)  # modelo e JSON valido
    assert "@@OIDC_CLIENT_SECRET@@" in modelo and "@@ORIS_DEMO_SENHA@@" in modelo
    env = {"ORIS_DOMAIN": "teste.exemplo.com", "OIDC_CLIENT_SECRET": "segredo-x", "ORIS_DEMO_SENHA": "senha-y",
           "LDAP_ADMIN_PASSWORD": "senha-ldap-z",
           "PATH": "/usr/bin:/bin"}
    destino = RAIZ / "docker" / "keycloak" / "generated"
    try:
        subprocess.run([sys.executable, str(RAIZ / "docker" / "keycloak" / "gerar-realm.py")],
                       check=True, env=env, capture_output=True)
        gerado = json.loads((destino / "oris-realm.json").read_text(encoding="utf-8"))
        assert "@@" not in json.dumps(gerado)
        assert gerado["clients"][0]["redirectUris"] == ["https://teste.exemplo.com/login/oidc/callback"]
        assert gerado["clients"][0]["attributes"]["pkce.code.challenge.method"] == "S256"
        ldap = gerado["components"]["org.keycloak.storage.UserStorageProvider"][0]["config"]
        assert ldap["bindCredential"] == ["senha-ldap-z"]
    finally:
        import shutil

        shutil.rmtree(destino, ignore_errors=True)


def test_gitignore_protege_segredos_gerados():
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for item in (".env.aws", "docker/ldap/certs/", "docker/keycloak/generated/"):
        assert item in ignorados


def test_laboratorio_visual_protege_consoles_e_nao_tem_segredo_padrao():
    compose = (RAIZ / "docker-compose.lab.yml").read_text(encoding="utf-8")
    for var in ("DB_PASSWORD", "DB_ROOT_PASSWORD", "SECRET_KEY", "DATA_ENCRYPTION_KEY", "SENHA_ADMIN", "MEU_IP", "ORIS_DOMAIN"):
        assert f"${{{var}:?" in compose, f"{var} deve ser obrigatoria (sem valor padrao)"
    # So o Caddy publica portas: LDAP, Keycloak, phpLDAPadmin, app e banco ficam na rede interna.
    import re

    servicos = compose.split("\nservices:\n", 1)[1].split("\nvolumes:\n", 1)[0]
    blocos = re.split(r"\n(?=  [a-z]+:\n)", "\n" + servicos)
    publicam = [b.strip().split(":")[0] for b in blocos if "\n    ports:" in b]
    assert publicam == ["caddy"], publicam
    assert "LDAP_USE_STARTTLS: \"true\"" in compose and "LDAP_CA_CERT_FILE" in compose
    assert "KC_TRUSTSTORE_PATHS" in compose and "kc_data:/opt/keycloak/data" in compose
    caddy = (RAIZ / "docker" / "Caddyfile.lab").read_text(encoding="utf-8")
    assert "not remote_ip {$MEU_IP}" in caddy and "path /admin* /realms/master*" in caddy
    assert "Strict-Transport-Security" in caddy


def test_user_data_do_laboratorio_exige_preencher_e_nao_traz_segredo():
    script = (RAIZ / "docker" / "lab" / "user-data.sh").read_text(encoding="utf-8")
    assert 'SENHA_ADMIN="TROQUE_POR_UMA_SENHA_FORTE"' in script  # placeholder, nunca uma senha real
    assert "*COLE_*|*TROQUE_*" in script  # recusa rodar sem preencher
    assert "chmod 600 .env.lab" in script and "openssl rand" in script
