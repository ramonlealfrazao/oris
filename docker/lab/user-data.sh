#!/bin/bash
# =====================================================================
# ORIS - LABORATORIO VISUAL (LDAP + OIDC + S3) - roteiro de instalacao
# =====================================================================
# Cole TODO este arquivo no campo "User data" (Advanced details) ao criar a
# instancia EC2. Ele roda sozinho na primeira vez que o servidor liga:
# instala o Docker, baixa o ORIS do GitHub e liga ORIS + LDAP + Keycloak.
# Leva de 5 a 10 minutos. Passo a passo completo: docs/LAB_VISUAL.md
#
# ANTES DE COLAR, PREENCHA AS 3 LINHAS ABAIXO (entre as aspas):
ELASTIC_IP="COLE_O_ELASTIC_IP_AQUI"     # ex.: 54.123.45.67 (Fase 1.2 do guia)
MEU_IP="COLE_O_SEU_IP_AQUI"             # abra https://checkip.amazonaws.com e copie
SENHA_ADMIN="TROQUE_POR_UMA_SENHA_FORTE"  # so letras, numeros e - _ . @ (minimo 12)
# Essa senha vale para: console do Keycloak (usuario admin), phpLDAPadmin
# (cn=admin,dc=oris,dc=local) e os usuarios de demonstracao do ORIS.
# Atencao: o conteudo do "User data" fica visivel no console da AWS para quem
# tem acesso a esta conta. Use uma senha so deste laboratorio.
# =====================================================================

set -eu
echo "[oris-lab] inicio $(date)"

case "$ELASTIC_IP$MEU_IP$SENHA_ADMIN" in
  *COLE_*|*TROQUE_*) echo "[oris-lab] ERRO: preencha ELASTIC_IP, MEU_IP e SENHA_ADMIN"; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 git openssl python3
systemctl enable --now docker

git clone https://github.com/ramonlealfrazao/oris.git /opt/oris
cd /opt/oris

DOMINIO="$(echo "$ELASTIC_IP" | tr '.' '-').sslip.io"
sh docker/ldap/gerar-certs.sh docker/ldap/certs

CHAVE_DADOS="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
cat > .env.lab <<FIM
ORIS_DOMAIN=$DOMINIO
MEU_IP=$MEU_IP
SENHA_ADMIN=$SENHA_ADMIN
DB_PASSWORD=$(openssl rand -hex 16)
DB_ROOT_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
DATA_ENCRYPTION_KEY=$CHAVE_DADOS
OIDC_ENABLED=false
OIDC_CLIENT_SECRET=
S3_BUCKET=
FIM
chmod 600 .env.lab

docker compose -f docker-compose.lab.yml --env-file .env.lab up -d --build

echo "[oris-lab] PRONTO $(date)"
echo "[oris-lab] ORIS:          https://$DOMINIO"
echo "[oris-lab] Keycloak:      https://kc.$DOMINIO/admin"
echo "[oris-lab] phpLDAPadmin:  https://ldap.$DOMINIO"
