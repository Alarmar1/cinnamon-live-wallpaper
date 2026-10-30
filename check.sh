# Получаем ID активного окна
WID=$(xprop -root _NET_ACTIVE_WINDOW | awk '{print $NF}')

# Проверяем наличие _NET_WM_STATE_FULLSCREEN в свойствах окна
if xprop -id "$WID" _NET_WM_STATE | grep -qw "_NET_WM_STATE_FULLSCREEN"; then
    echo "Окно в полноэкранном режиме"
else
    echo "Окно не в полноэкранном режиме"
fi
