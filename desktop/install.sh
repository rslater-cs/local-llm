#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin="$project_dir/.venv/bin/python"
bin_dir="$HOME/.local/bin"
applications_dir="$HOME/.local/share/applications"
autostart_dir="$HOME/.config/autostart"
icons_dir="$HOME/.local/share/icons/hicolor/scalable/apps"

if [ ! -x "$python_bin" ]; then
    echo "Missing project virtual environment: $project_dir/.venv" >&2
    echo "Create it with: python3 -m venv .venv" >&2
    exit 1
fi
if ! "$python_bin" -c 'import PySide6' >/dev/null 2>&1; then
    echo "PySide6 is required in the project virtual environment." >&2
    echo "Install it with: .venv/bin/pip install PySide6" >&2
    exit 1
fi
mkdir -p "$bin_dir" "$applications_dir" "$autostart_dir" "$icons_dir"
printf '#!/usr/bin/env bash\ncd "%s"\nexec "%s" -m app.main\n' "$project_dir" "$python_bin" > "$bin_dir/local-llm-tray"
chmod 755 "$bin_dir/local-llm-tray"
sed "s|Exec=local-llm-tray|Exec=$bin_dir/local-llm-tray|" "$project_dir/desktop/local-llm.desktop" > "$applications_dir/local-llm.desktop"
sed "s|Exec=local-llm-tray|Exec=$bin_dir/local-llm-tray|" "$project_dir/desktop/local-llm-autostart.desktop" > "$autostart_dir/local-llm.desktop"
install -m 644 "$project_dir/app/resources/icons/local-llm.svg" "$icons_dir/local-llm.svg"
echo "Desktop launcher and autostart entry installed for $project_dir"
