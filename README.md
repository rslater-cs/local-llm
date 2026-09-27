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

## Desktop tray controller

The repository includes a small PySide6 tray controller. It manages the existing
Docker Compose project and does not start containers merely because the tray app
is launched.

Use a project-local virtual environment (Linux Mint protects its system Python),
then run from the repository:

```bash
python3 -m venv .venv
.venv/bin/pip install PySide6
.venv/bin/python -m app.main
```

Use `.venv/bin/python -m app.main` when starting it manually. The desktop
installer uses that same virtual environment.

The **Model** menu recursively discovers `.gguf` files in `models/`. Selecting a
model writes the application-owned `.local-llm.env` file and invokes `docker
compose up -d`; Compose recreates only the affected service(s). Advanced settings
remain in `.env` and `compose.yaml`.

To install a per-user desktop launcher and XDG autostart entry, run:

```bash
./desktop/install.sh
```

The tray application's **Stop** action uses `docker compose stop`; **Quit** only
closes the tray application and leaves containers running. Open WebUI uses the
`OPENWEBUI_PORT` in `.env`, defaulting to `http://localhost:3000`.

On Fedora GNOME, tray icons may require an enabled AppIndicator/StatusNotifier
GNOME Shell extension. The application warns if Qt reports no tray support; it
does not install or change GNOME extensions.
