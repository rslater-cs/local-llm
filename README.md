# Local AI Stack

Portable local LLM environment.

Supported:
- Linux Mint
- Fedora
- Ubuntu
- Debian

## Architecture

VS Code
 |
Continue
 |
LiteLLM
 |
llama.cpp
 |
GGUF model


Open WebUI also connects through LiteLLM.

## Setup

Clone:

git clone <repo>

cd local-ai-stack


Run:

./setup.sh


Add model:

models/model.gguf


Build:

make build


Start:

make up


Open:

http://localhost:3000


## Updating

make update


## Changing models

Edit:

.env

Change:

MODEL_FILE=