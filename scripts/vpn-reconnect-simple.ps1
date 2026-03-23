# FortiClient VPN Auto-Reconnect - Простая версия
# Без дополнительных модулей, только встроенный .NET

# === НАСТРОЙКИ ===
$CheckHosts = @("10.4.56.1", "10.4.56.2", "8.8.8.8")  # хосты для проверки
$CheckTimeout = 3          # таймаут пинга
$CheckInterval = 300       # интервал проверки (5 минут)
$LogFile = "C:\Scripts\vpn-reconnect.log"

# === ЗАГРУЗКА UI AUTOMATION ===
Add-Type -AssemblyName System.Windows.Automation
Add-Type -AssemblyName System.Windows.Forms

# === ПРОВЕРКА VPN ===
function Test-VPNWorking {
    foreach ($host in $CheckHosts) {
        try {
            $ping = Test-Connection -ComputerName $host -Count 1 -Quiet -TimeoutSeconds $CheckTimeout -ErrorAction Stop
            if ($ping) {
                return $true
            }
        } catch {}
    }
    return $false
}

# === ПОИСК И КЛИК ПО КНОПКЕ ===
function Click-FortiConnect {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content $LogFile "$time : Searching for FortiClient Connect button..."
    
    # Ищем процесс FortiClient
    $fortiProc = Get-Process -Name "FortiClient" -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if (-not $fortiProc) {
        Add-Content $LogFile "$time : FortiClient not running, starting..."
        Start-Process "C:\Program Files\Fortinet\FortiClient\FortiClient.exe"
        Start-Sleep -Seconds 6
    }
    
    # Получаем главное окно
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, (Get-Process -Name "FortiClient" -ErrorAction SilentlyContinue | Select-Object -First 1).Id)
    $automationElement = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children, $condition)
    
    if ($automationElement) {
        # Ищем кнопку Connect
        $buttonCondition = New-Object System.Windows.Automation.AndCondition(@(
            (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)),
            (New-Object System.Windows.Automation.OrCondition(@(
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "Connect")),
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "Connect VPN")),
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "Disconnected"))
            )))
        ))
        
        $button = $automationElement.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $buttonCondition)
        
        if ($button) {
            $buttonName = $button.Current.Name
            Add-Content $LogFile "$time : Found button '$buttonName', clicking..."
            
            # Клик через InvokePattern
            $invokePattern = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $invokePattern.Invoke()
            
            Add-Content $LogFile "$time : Clicked successfully"
            return $true
        }
        
        # Альтернатива: шлём клавиши
        Add-Content $LogFile "$time : Button not found, using keyboard..."
        
        # Активируем окно и шлём Alt+C
        $window = $automationElement.FindFirst([System.Windows.Automation.TreeScope]::Element, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Window)))
        if ($window) {
            $window.SetFocus()
            Start-Sleep -Milliseconds 300
            [System.Windows.Forms.SendKeys]::SendWait("%c")  # Alt+C
            Add-Content $LogFile "$time : Sent Alt+C"
            return $true
        }
    }
    
    Add-Content $LogFile "$time : Failed to find/click button"
    return $false
}

# === MAIN ===
if (-not (Test-Path (Split-Path $LogFile -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $LogFile -Parent) -Force | Out-Null
}

Add-Content $LogFile "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : Starting VPN monitor..."

while ($true) {
    if (Test-VPNWorking) {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : VPN OK"
    } else {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : VPN DOWN - clicking Connect..."
        Click-FortiConnect
    }
    
    Start-Sleep -Seconds $CheckInterval
}
