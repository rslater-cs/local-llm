#!/usr/bin/env bash

set -euo pipefail

echo "=== Local AI Stack Setup ==="

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
else
    echo "Cannot detect operating system"
    exit 1
fi


echo "Detected: $NAME"


# Install Docker on Debian/Ubuntu/Mint
if command -v apt >/dev/null; then

    echo "Installing Docker using apt..."

    sudo apt update

    sudo apt install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git

    # Add Docker repository key if Docker is not already installed
    if ! command -v docker >/dev/null; then

        sudo install -m 0755 -d /etc/apt/keyrings

        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

        sudo chmod a+r /etc/apt/keyrings/docker.gpg

        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
          https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
          | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

        sudo apt update

        sudo apt install -y \
            docker-ce \
            docker-ce-cli \
            containerd.io \
            docker-buildx-plugin \
            docker-compose-plugin

    else
        echo "Docker already installed"
    fi


# Install Docker on Fedora
elif command -v dnf >/dev/null; then

    echo "Installing Docker using dnf..."

    sudo dnf install -y dnf-plugins-core git

    sudo dnf config-manager \
        --add-repo \
        https://download.docker.com/linux/fedora/docker-ce.repo

    sudo dnf install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

else

    echo "Unsupported distribution"
    exit 1

fi


echo "Starting Docker service..."

sudo systemctl enable docker
sudo systemctl start docker


echo "Adding current user to docker group..."

sudo usermod -aG docker "$USER"


echo "Creating directories..."

mkdir -p models
mkdir -p data/open-webui
mkdir -p data/litellm


if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
fi


echo
echo "=== Setup complete ==="
echo
echo "IMPORTANT:"
echo "Log out and back in for Docker group permissions to apply."
echo
echo "Then run:"
echo
echo "  docker compose build"
echo "  docker compose up -d"
echo