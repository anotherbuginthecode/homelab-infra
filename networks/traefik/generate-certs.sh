#!/bin/bash

DOMAIN_NAME=$1

mkdir -p ~/certs && cd ~/certs

echo "Creating local CA..."
openssl genrsa -out homelabCA.key 4096

openssl req -x509 -new -nodes \
  -key homelabCA.key \
  -sha256 -days 3650 \
  -out homelabCA.pem \
  -subj "/C=IT/ST=Italy/L=Home/O=Homelab/OU=Dev/CN=Homelab Root CA"


echo "Generating wildcard certifcate..."
cat > ${DOMAIN_NAME}.cnf << EOF
[ req ]
default_bits       = 4096
prompt             = no
default_md         = sha256
req_extensions     = req_ext
distinguished_name = dn

[ dn ]
C  = IT
ST = Italy
L  = Home
O  = Homelab
OU = Dev
CN = $DOMAIN_NAME

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = $DOMAIN_NAME
DNS.2 = *.$DOMAIN_NAME
EOF

openssl genrsa -out $DOMAIN_NAME.key 4096

openssl req -new \
  -key $DOMAIN_NAME.key \
  -out $DOMAIN_NAME.csr \
  -config $DOMAIN_NAME.cnf

openssl x509 -req \
  -in $DOMAIN_NAME.csr \
  -CA homelabCA.pem \
  -CAkey homelabCA.key \
  -CAcreateserial \
  -out $DOMAIN_NAME.crt \
  -days 825 \
  -sha256 \
  -extensions req_ext \
  -extfile $DOMAIN_NAME.cnf

