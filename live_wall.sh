#!/usr/bin/env bash
# Живые обои (linux-wallpaperengine) под иконками рабочего стола на Cinnamon (X11).
#
# Использование:
#   ./live_wall.sh <ID_обоев_или_путь_к_папке> [FPS] [VOLUME]
#   ./live_wall.sh --fix-icons    повторить только последовательность с иконками
#
# Зависимости: linux-wallpaperengine, wmctrl, x11-utils (xprop), xdotool
#   sudo apt install wmctrl x11-utils xdotool

set -u

# ---- Настройки ----
OUTPUT="HDMI-0"      # только для справки, окно позиционируется по X/Y/W/H
X=0
Y=0
W=1920
H=1080
FPS=30
VOLUME=10
START_DELAY=5
ICONS_OFF="false::false"
ICONS_ON="true::false"
# -------------------

for cmd in linux-wallpaperengine wmctrl xprop xdotool gsettings; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Не найдено: $cmd"; exit 1; }
done

# Окно терминала, из которого запущен скрипт (если запуск из терминала)
TERM_WID=""
if [ -t 0 ]; then
    TERM_WID=$(xdotool getactivewindow 2>/dev/null || echo "${WINDOWID:-}")
fi

find_wid() {
    local pid="$1" wid=""
    for _ in $(seq 1 30); do
        wid=$(wmctrl -lp | awk -v pid="$pid" '$3 == pid {print $1; exit}')
        [ -n "$wid" ] && { echo "$wid"; return 0; }
        sleep 0.1
    done
    return 1
}

# Схема: свернуть терминал -> иконки выкл -> 0.5с -> иконки вкл -> 0.5с -> развернуть терминал
icons_cycle() {
    if [ -n "$TERM_WID" ]; then
        xdotool windowminimize "$TERM_WID"
        sleep 0.1
    fi

    gsettings set org.nemo.desktop desktop-layout "$ICONS_OFF"
    sleep 0.5
    gsettings set org.nemo.desktop desktop-layout "$ICONS_ON"
    sleep 0.5

    if [ -n "$TERM_WID" ]; then
        xdotool windowactivate "$TERM_WID"
    fi
}

# ---- Режим --fix-icons ----
if [ "${1:-}" = "--fix-icons" ]; then
    sleep 5
    icons_cycle
    echo "Готово."
    exit 0
fi

if [ "${1:-}" = "--fix-icons-express" ]; then
    icons_cycle
    echo "Готово."
    exit 0
fi

WALLPAPER="${1:-}"
FPS="${2:-30}"
VOLUME="${3:-10}"
if [ -z "$WALLPAPER" ]; then
    echo "Укажи ID обоев или путь к папке: $0 <ID|путь>"
    exit 1
fi

sleep "$START_DELAY"

# Останавливаем предыдущий запуск, если был
#pkill -x linux-wallpaperengine 2>/dev/null
#sleep 0.1

# 1. Запуск обоев
linux-wallpaperengine --window "${X}x${Y}x${W}x${H}" --fps "$FPS" --volume "$VOLUME" "$WALLPAPER" &
PID=$!

WID=$(find_wid "$PID")
if [ -z "$WID" ]; then
    echo "Окно не найдено. Список окон с PID:"
    wmctrl -lp
    exit 1
fi
echo "Окно обоев: $WID ($OUTPUT, ${W}x${H})"

# 2. Размещение
wmctrl -i -r "$WID" -e "0,${X},${Y},${W},${H}"

# 3. Слой: тип "рабочий стол" (скрыть -> сменить -> показать), затем "под всем"
xdotool windowunmap "$WID"
xprop -id "$WID" -f _NET_WM_WINDOW_TYPE 32a \
    -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_DESKTOP
xdotool windowmap "$WID"
sleep 0.1
wmctrl -i -r "$WID" -b add,below,sticky,skip_taskbar,skip_pager
wmctrl -i -r "$WID" -e "0,${X},${Y},${W},${H}"
# 4. Иконки: свернуть терминал, выкл, вкл, развернуть терминал
sleep 1
icons_cycle

echo "Готово. Остановить: pkill -x linux-wallpaperengine"
wait "$PID"
