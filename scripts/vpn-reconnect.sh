#!/bin/bash
# FortiClient VPN Auto-Reconnect Script
# Проверяет VPN и переподключает если нужно

# === НАСТРОЙКИ ===
VPN_CHECK_HOST="8.8.8.8"          # хост для проверки (через VPN)
VPN_CHECK_INTERVAL=300            # проверять каждые 5 минут
FORTICLIENT_WINDOW="FortiClient"  # имя окна

# === ПРОВЕРКА VPN ===
check_vpn() {
    # Вариант 1: пингуем через VPN интерфейс
    # ping -I <VPN_interface> -c 1 -W 2 8.8.8.8 >/dev/null 2>&1
    
    # Вариант 2: просто пинг
    if ping -c 1 -W 3 "$VPN_CHECK_HOST" >/dev/null 2>&1; then
        return 0  # VPN работает
    else
        return 1  # VPN не работает
    fi
}

# === ПОДКЛЮЧЕНИЕ ===
reconnect_vpn() {
    echo "$(date): VPN down, reconnecting..."
    
    # Способ 1: xdotool (если есть графика)
    if command -v xdotool &> /dev/null; then
        # Ищем окно FortiClient
        wid=$(xdotool search --name "$FORTICLIENT_WINDOW" | head -1)
        if [ -n "$wid" ]; then
            xdotool windowactivate "$wid"
            sleep 1
            # Ищем кнопку "Connect" и кликаем
            xdotool key --window "$wid" --delay 100 Tab Tab Tab space
            # или клик по координатам (нужно подстроить)
            # xdotool mousemove --window "$wid" 300 150 click 1
            echo "$(date): Clicked Connect via xdotool"
        fi
    fi
    
    # Способ 2: FortiClient CLI (если есть)
    if [ -f "/Applications/FortiClient.app/Contents/MacOS/FortiClient" ]; then
        # macOS
        /Applications/FortiClient.app/Contents/MacOS/FortiClient -c "Corporate VPN"
    elif command -v forticlient &> /dev/null; then
        # Linux CLI
        forticlient --connect "Corporate VPN"
    fi
}

# === MAIN ===
echo "$(date): Starting VPN monitor..."

while true; do
    if check_vpn; then
        echo "$(date): VPN OK"
    else
        reconnect_vpn
    fi
    sleep "$VPN_CHECK_INTERVAL"
done
