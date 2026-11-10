#!/bin/sh
# Gera a CA e o certificado do LDAP do laboratorio (validade 1 ano). Uso: sh gerar-certs.sh <pasta-de-saida>
# O certificado vale para ldap.oris.local (nome usado dentro da rede do Docker) e localhost.
set -e
OUT="${1:?informe a pasta de saida}"
mkdir -p "$OUT"
cd "$OUT"
openssl genrsa -out ca.key 4096 2>/dev/null
openssl req -x509 -new -key ca.key -sha256 -days 365 -subj "/O=ORIS Laboratorio/CN=ORIS Lab CA" -out ca.crt
openssl genrsa -out ldap.key 2048 2>/dev/null
openssl req -new -key ldap.key -subj "/O=ORIS Laboratorio/CN=ldap.oris.local" -out ldap.csr
printf "subjectAltName=DNS:ldap.oris.local,DNS:localhost\nextendedKeyUsage=serverAuth\n" > ext.cnf
openssl x509 -req -in ldap.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out ldap.crt -days 365 -sha256 -extfile ext.cnf 2>/dev/null
rm -f ldap.csr ext.cnf ca.srl ca.key
# o contêiner do LDAP roda como outro usuario e precisa ler a chave
chmod 644 ca.crt ldap.crt ldap.key
echo "Certificados gerados em $OUT (ca.crt, ldap.crt, ldap.key). A chave da CA foi descartada de proposito."
