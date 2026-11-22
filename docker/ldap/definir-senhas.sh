#!/bin/sh
set -e
: "${LDAP_ADMIN_PASSWORD:?defina LDAP_ADMIN_PASSWORD}"
: "${ORIS_DEMO_SENHA:?defina ORIS_DEMO_SENHA}"
COMPOSE="sudo docker compose -f docker-compose.aws.yml -f docker-compose.idp.yml --env-file .env.aws"
for uid in ana.admin bruno.gestao carla.saude davi.gestor eva.semgrupo; do
  $COMPOSE exec -T -e SENHA_ADMIN="$LDAP_ADMIN_PASSWORD" -e SENHA_NOVA="$ORIS_DEMO_SENHA" ldap \
    sh -c 'ldappasswd -x -H ldap://localhost -D cn=admin,dc=oris,dc=local -w "$SENHA_ADMIN" -s "$SENHA_NOVA" "uid='"$uid"',ou=usuarios,dc=oris,dc=local"'
  echo "senha definida: $uid"
done
