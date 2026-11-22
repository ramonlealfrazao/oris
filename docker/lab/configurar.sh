#!/bin/sh
# Atalhos do laboratorio visual (um comando cada, no terminal da EC2):
#   sudo sh /opt/oris/docker/lab/configurar.sh oidc SEGREDO_DO_CLIENT   -> liga o login institucional (Fase 6)
#   sudo sh /opt/oris/docker/lab/configurar.sh s3 NOME_DO_BUCKET        -> liga a exportacao ao S3 (Fase 7)
#   sudo sh /opt/oris/docker/lab/configurar.sh ip SEU_NOVO_IP           -> seu IP mudou e os consoles deram 403
#   sudo sh /opt/oris/docker/lab/configurar.sh enderecos                -> mostra os enderecos do laboratorio
set -eu
cd "$(dirname "$0")/../.."
ENV=.env.lab
[ -f "$ENV" ] || { echo "Nao achei $ENV em $(pwd). O user-data rodou?"; exit 1; }

definir() {
  chave="$1"; valor="$2"
  case "$valor" in *"|"*|*" "*|"") echo "Valor invalido para $chave."; exit 1 ;; esac
  if grep -q "^$chave=" "$ENV"; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$ENV"
  else
    echo "$chave=$valor" >> "$ENV"
  fi
}

COMPOSE="docker compose -f docker-compose.lab.yml --env-file $ENV"
case "${1:-}" in
  oidc)
    definir OIDC_CLIENT_SECRET "${2:-}"
    definir OIDC_ENABLED true
    $COMPOSE up -d app
    echo "Login institucional ligado: o botao 'Entrar com login institucional (SSO)' aparece na tela de login."
    ;;
  s3)
    definir S3_BUCKET "${2:-}"
    $COMPOSE up -d app
    echo "Exportacao ao S3 ligada para o bucket ${2}."
    ;;
  ip)
    definir MEU_IP "${2:-}"
    $COMPOSE up -d caddy
    echo "Consoles liberados para o IP ${2}."
    ;;
  enderecos)
    D="$(grep '^ORIS_DOMAIN=' "$ENV" | cut -d= -f2)"
    echo "ORIS:          https://$D"
    echo "Keycloak:      https://kc.$D/admin"
    echo "phpLDAPadmin:  https://ldap.$D"
    ;;
  *)
    sed -n '2,6p' "$0"; exit 1 ;;
esac
