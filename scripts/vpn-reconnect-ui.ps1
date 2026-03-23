# FortiClient VPN Auto-Reconnect with UI Automation
# Только PowerShell, без дополнительных программ

# === НАСТРОЙКИ ===
$CheckHosts = @("10.4.56.1", "10.4.56.2", "8.8.8.8")  # хосты для проверки VPN
$CheckTimeout = 3          # таймаут пинга в секундах
$CheckInterval = 300       # интервал проверки в секундах (5 минут)
$LogFile = "C:\Scripts\vpn-reconnect.log"

# === ЗАГРУЗКА UI AUTOMATION ===
Add-Type -AssemblyName System.Windows.Automation

# === ПРОВЕРКА VPN ===
function Test-VPNWorking {
    foreach ($host in $CheckHosts) {
        $ping = Test-Connection -ComputerName $host -Count 1 -Quiet -TimeoutSeconds $CheckTimeout
        if ($ping) {
            return $true
        }
    }
    return $false
}

# === НАЖАТИЕ КНОПКИ CONNECT ===
function Click-ConnectButton {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content $LogFile "$time : Looking for FortiClient Connect button..."
    
    # Ищем все окна
    $fortiWindows = Get-UIAWindow -Name "*FortiClient*"
    
    if (-not $fortiWindows) {
        Add-Content $LogFile "$time : FortiClient window not found, trying to start it..."
        Start-Process "C:\Program Files\Fortinet\FortiClient\FortiClient.exe"
        Start-Sleep -Seconds 5
        $fortiWindows = Get-UIAWindow -Name "*FortiClient*"
    }
    
    if ($fortiWindows) {
        # Способ 1: ищем кнопку по имени (может отличаться)
        # В FortiClient 7.x кнопка часто называется "Connect" или "Disconnect"
        
        try {
            # Ищем кнопку внутри окна
            $button = Get-UIAControl -AutomationElement $fortiWindows -ControlType Button | Where-Object { 
                $_.Current.Name -match "Connect" -or $_.Current.Name -match "Disconnected"
            } | Select-Object -First 1
            
            if ($button) {
                Add-Content $LogFile "$time : Found button: $($button.Current.Name), clicking..."
                $button | Invoke-UIAControlClick
                Add-Content $LogFile "$time : Clicked Connect button"
                return $true
            }
        } catch {
            # Если не нашли через UI Automation, пробуем xdotool-like через SendKeys
            Add-Content $LogFile "$time : UI Automation failed, trying keyboard method..."
        }
        
        # Способ 2: активируем окно и шлём клавишу
        $fortiWindows | Set-UIAFocus
        Start-Sleep -Milliseconds 500
        # Нажимаем Tab пока не дойдём до кнопки, потом Enter
        [System.Windows.Forms.SendKeys]::SendWait("{TAB}")
        Start-Sleep -Milliseconds 200
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
        Add-Content $LogFile "$time : Sent keyboard shortcut"
        return $true
    }
    
    Add-Content $LogFile "$time : Could not find FortiClient window"
    return $false
}

# === MAIN ===
Add-Content $LogFile "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : Starting VPN monitor (UI Automation)..."

# Загружаем Windows.Forms для SendKeys
Add-Type -AssemblyName System.Windows.Forms

while ($true) {
    if (Test-VPNWorking) {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : VPN OK"
    } else {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : VPN DOWN - clicking Connect..."
        Click-ConnectButton
    }
    
    Start-Sleep -Seconds $CheckInterval
}
