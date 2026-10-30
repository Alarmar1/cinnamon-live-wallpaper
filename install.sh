#!/usr/bin/env bash
# Установка cinnamon-live-wallpaper как приложения для меню (локальная установка).
#
# Что делает:
#   1. Копирует app.py и live_wall.sh в ~/.local/share/cinnamon-live-wallpaper/
#   2. Создает .desktop-файл в ~/.local/share/applications/
#
# Запуск: ./install.sh   (или ./install.sh --uninstall для удаления)

set -euo pipefail

APP_ID="cinnamon-live-wallpaper"
APP_NAME="Cinnamon Live Wallpaper"
INSTALL_DIR="${HOME}/.local/share/cinnamon-live-wallpaper"
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/${APP_ID}.desktop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" = "--uninstall" ]]; then
    rm -rf "$INSTALL_DIR"
    rm -f "$DESKTOP_FILE"
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    echo "Удалено: $INSTALL_DIR и $DESKTOP_FILE"
    exit 0
fi

# --- 1. Файлы приложения ---
mkdir -p "$INSTALL_DIR"
install -m 755 "$SCRIPT_DIR/app.py" "$INSTALL_DIR/app.py"
install -m 755 "$SCRIPT_DIR/live_wall.sh" "$INSTALL_DIR/live_wall.sh"

# Переносим текущее состояние (последние обои), чтобы настройки не сбрасывались
if [[ -f "$SCRIPT_DIR/last.json" && ! -f "$INSTALL_DIR/last.json" ]]; then
    cp "$SCRIPT_DIR/last.json" "$INSTALL_DIR/last.json"
fi

# --- 2. Ярлык для меню ---
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
Name[ru]=Cinnamon Live Wallpaper
Comment=Live wallpapers from Wallpaper Engine workshop
Comment[ru]=Живые обои из мастерской Wallpaper Engine
Exec=${INSTALL_DIR}/app.py
Path=${INSTALL_DIR}
TryExec=${INSTALL_DIR}/app.py
Icon=preferences-desktop-wallpaper
StartupWMClass=${APP_ID}
Terminal=false
Categories=GNOME;GTK;Utility;DesktopSettings;
Keywords=wallpaper;обои;wallpaper engine;
NoDisplay=false
EOF
chmod 644 "$DESKTOP_FILE"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Установлено:"
echo "  Файлы:     $INSTALL_DIR"
echo "  Ярлык:     $DESKTOP_FILE"
echo "Проверить:   gtk-launch ${APP_ID}   (или найти в меню по имени «${APP_NAME}»)"
