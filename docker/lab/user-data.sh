#!/bin/bash
ELASTIC_IP="COLE_O_ELASTIC_IP_AQUI"
MEU_IP="COLE_O_SEU_IP_AQUI"
SENHA_ADMIN="TROQUE_POR_UMA_SENHA_FORTE"

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
