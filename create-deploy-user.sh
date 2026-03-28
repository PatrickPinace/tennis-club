#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_USER="deploy"
DEPLOY_HOME="/home/${DEPLOY_USER}"

if id "$DEPLOY_USER" >/dev/null 2>&1; then
  echo "User ${DEPLOY_USER} already exists"
else
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  echo "Created user ${DEPLOY_USER}"
fi

usermod -aG docker "$DEPLOY_USER"

mkdir -p "$DEPLOY_HOME/.ssh"
chmod 700 "$DEPLOY_HOME/.ssh"
touch "$DEPLOY_HOME/.ssh/authorized_keys"
chmod 600 "$DEPLOY_HOME/.ssh/authorized_keys"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_HOME/.ssh"

mkdir -p /opt/apps/tennis-club
chown -R "$DEPLOY_USER:$DEPLOY_USER" /opt/apps/tennis-club

echo
echo "User ${DEPLOY_USER} is ready."
echo "Now append the GitHub Actions public SSH key to:"
echo "  ${DEPLOY_HOME}/.ssh/authorized_keys"
echo
