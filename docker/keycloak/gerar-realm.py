#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
VARS = ("ORIS_DOMAIN", "OIDC_CLIENT_SECRET", "ORIS_DEMO_SENHA", "LDAP_ADMIN_PASSWORD")


def main():
    faltando = [v for v in VARS if not os.environ.get(v)]
    if faltando:
        sys.exit(f"Defina no ambiente: {', '.join(faltando)}")
    texto = (PASTA / "oris-realm.template.json").read_text(encoding="utf-8")
    dados = json.loads(texto)

    def trocar(valor):
        if isinstance(valor, str):
            return re.sub(r"@@(\w+)@@", lambda m: os.environ[m.group(1)], valor)
        if isinstance(valor, list):
            return [trocar(v) for v in valor]
        if isinstance(valor, dict):
            return {k: trocar(v) for k, v in valor.items()}
        return valor

    saida = PASTA / "generated"
    saida.mkdir(exist_ok=True)
    destino = saida / "oris-realm.json"
    destino.write_text(json.dumps(trocar(dados), ensure_ascii=False, indent=2), encoding="utf-8")
    destino.chmod(0o644)
    print(f"Gerado {destino}")


if __name__ == "__main__":
    main()
