#!/usr/bin/env bash

set -e


git pull

podman compose pull

podman compose build

podman compose up -d