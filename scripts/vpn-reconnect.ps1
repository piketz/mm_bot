# FortiClient VPN Auto-Reconnect Script
# Положи в C:\Scripts\vpn-reconnect.ps1 и запускай

# === НАСТРОЙКИ ===
$CheckHost = "8.8.8.8"          # хост для проверки
$CheckInterval = 300            # интервал в секундах (5 минут)
$LogFile = "C:\Scripts\vpn-reconnect.log"

# === ПРОВЕРКА VPN ===
function Test-VPN {
    # Вариант 1: пинг
    $ping = Test-Connection -ComputerName $CheckHost -Count 1 -Quiet -ErrorAction SilentlyContinue
    
    # Вариант 2: проверка маршрута до хоста
    # $route = Test-NetRoute -DestinationPrefix "8.8.8.8/32" -ErrorAction SilentlyContinue
    
    return $ping
}

# === ПЕРЕПОДКЛЮЧЕНИЕ ===
function Reconnect-VPN {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content $LogFile "$time : VPN down, reconnecting..."
    
    # Способ 1: Перезапуск FortiClient процессов
    $fortiProcs = Get-Process | Where-Object { $_.Name -match "FortiClient|FortiSSL|FortiTray" -ErrorAction SilentlyContinue }
    
    if ($fortiProcs) {
        Add-Content $LogFile "$time : Stopping FortiClient processes..."
        $fortiProcs | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }
    
    # Запуск FortiClient
    Add-Content $LogFile "$time : Starting FortiClient..."
    Start-Process "C:\Program Files\Fortinet\FortiClient\FortiClient.exe" -ErrorAction SilentlyContinue
    
    # Ждём загрузки
    Start-Sleep -Seconds 5
    
    # Нажатие кнопки Connect через UI (опционально)
    # Можно использовать AutoIt или UiPath, но сложнее
    
    Add-Content $LogFile "$time : Reconnect complete"
}

# === MAIN ===
Add-Content $LogFile "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : Starting VPN monitor..."

while ($true) {
    if (Test-VPN) {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : VPN OK"
    } else {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : VPN DOWN - reconnecting..."
        Reconnect-VPN
    }
    
    Start-Sleep -Seconds $CheckInterval
}
