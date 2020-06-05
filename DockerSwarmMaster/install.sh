#!/bin/bash

echo
echo Docker Installation
curl -sSL https://get.docker.com | sh

echo
echo Opening insecure access to the Docker Engine via HTTP
UNIT='docker.service'
DIR="/etc/systemd/system/${UNIT}.d"
sudo mkdir $DIR
{ echo "[Service]";
  echo "ExecStart=";
  echo "ExecStart=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock -H tcp://0.0.0.0:80";
} | sudo tee ${DIR}/override.conf
sudo systemctl daemon-reload

echo
echo Adding Insecure Docker Registry
read -p "Enter Docker Registry IP address or URL: " DOCKER_REGISTRY_IP
{ echo "{ \"insecure-registries\":[\"$DOCKER_REGISTRY_IP\"] }"; } | sudo tee /etc/docker/daemon.json

echo
echo Restart Docker
sudo service docker restart

echo
echo Enabling Swarm Mode
sudo docker swarm init --task-history-limit 0
