# =============================================================================
# MINI-SOC API CONNECTIVITY DIAGNOSTIC TOOL (PowerShell)
# =============================================================================

$ErrorActionPreference = "Continue"

# Colors
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[✓] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[⚠] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[✗] $args" -ForegroundColor Red }
function Write-Section {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " $args" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

# =============================================================================
# STEP 1: ĐỌC CẤU HÌNH
# =============================================================================

Write-Section "BƯỚC 1: Thu thập thông tin cấu hình"

$envFile = $null
if (Test-Path ".env.production") {
    $envFile = ".env.production"
} elseif (Test-Path "backend\.env") {
    $envFile = "backend\.env"
} else {
    Write-Error "Không tìm thấy file cấu hình"
    exit 1
}

Write-Info "Đọc cấu hình từ: $envFile"

# Parse .env file
$config = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        $config[$matches[1]] = $matches[2]
    }
}

Write-Success "Đã đọc cấu hình"

Write-Info "Cấu hình hiện tại:"
Write-Host "  WAZUH_API_URL     : $($config['WAZUH_API_URL'])"
Write-Host "  WAZUH_API_USER    : $($config['WAZUH_API_USER'])"
Write-Host "  ZABBIX_API_URL    : $($config['ZABBIX_API_URL'])"
Write-Host "  ZABBIX_ENABLED    : $($config['ZABBIX_ENABLED'])"

# =============================================================================
# STEP 2: KIỂM TRA WAZUH API
# =============================================================================

Write-Section "BƯỚC 2: Kiểm tra Wazuh API"

$wazuhStatus = "UNKNOWN"
$wazuhError = ""

if (-not $config['WAZUH_API_URL']) {
    Write-Error "WAZUH_API_URL không được cấu hình"
    $wazuhStatus = "NOT_CONFIGURED"
} else {
    $wazuhUrl = $config['WAZUH_API_URL']
    Write-Info "Testing Wazuh API: $wazuhUrl"
    
    # Extract host and port
    if ($wazuhUrl -match 'https?://([^:]+):?(\d+)?') {
        $wazuhHost = $matches[1]
        $wazuhPort = if ($matches[2]) { $matches[2] } else { "55000" }
        
        Write-Info "Wazuh Host: $wazuhHost"
        Write-Info "Wazuh Port: $wazuhPort"
        
        # Test 1: Network connectivity
        Write-Info "Test 1: Network connectivity..."
        if (Test-Connection -ComputerName $wazuhHost -Count 1 -Quiet -ErrorAction SilentlyContinue) {
            Write-Success "Host $wazuhHost is reachable"
        } else {
            Write-Warning "Cannot ping $wazuhHost (firewall may block ICMP)"
        }
        
        # Test 2: Port connectivity
        Write-Info "Test 2: Port connectivity..."
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        try {
            $tcpClient.Connect($wazuhHost, $wazuhPort)
            $tcpClient.Close()
            Write-Success "Port $wazuhPort is open on $wazuhHost"
        } catch {
            Write-Error "Cannot connect to port $wazuhPort on $wazuhHost"
            Write-Error "→ Wazuh API không chạy hoặc firewall chặn"
            $wazuhStatus = "PORT_CLOSED"
            $wazuhError = "Port $wazuhPort không mở"
        }
        
        # Test 3: HTTPS connectivity
        if ($wazuhStatus -ne "PORT_CLOSED") {
            Write-Info "Test 3: HTTPS connectivity..."
            
            try {
                # Skip SSL verification if needed
                add-type @"
                    using System.Net;
                    using System.Security.Cryptography.X509Certificates;
                    public class TrustAllCertsPolicy : ICertificatePolicy {
                        public bool CheckValidationResult(
                            ServicePoint srvPoint, X509Certificate certificate,
                            WebRequest request, int certificateProblem) {
                            return true;
                        }
                    }
"@
                [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
                [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
                
                $response = Invoke-WebRequest -Uri $wazuhUrl -Method Get -UseBasicParsing -ErrorAction Stop
                Write-Success "Wazuh API responds (HTTP $($response.StatusCode))"
            } catch {
                if ($_.Exception.Response.StatusCode.value__ -eq 401) {
                    Write-Success "Wazuh API responds (HTTP 401 - needs auth)"
                } else {
                    Write-Error "Cannot connect to Wazuh API: $($_.Exception.Message)"
                    $wazuhStatus = "HTTPS_FAILED"
                    $wazuhError = "HTTPS connection failed"
                }
            }
        }
        
        # Test 4: Authentication
        if ($wazuhStatus -notin @("PORT_CLOSED", "HTTPS_FAILED")) {
            Write-Info "Test 4: Authentication..."
            
            if (-not $config['WAZUH_API_USER'] -or -not $config['WAZUH_API_PASSWORD']) {
                Write-Error "WAZUH_API_USER hoặc WAZUH_API_PASSWORD không được set"
                $wazuhStatus = "NO_CREDENTIALS"
            } else {
                try {
                    $credentials = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($config['WAZUH_API_USER']):$($config['WAZUH_API_PASSWORD'])"))
                    $headers = @{ Authorization = "Basic $credentials" }
                    
                    $authUrl = "$wazuhUrl/security/user/authenticate"
                    $authResponse = Invoke-RestMethod -Uri $authUrl -Method Get -Headers $headers -UseBasicParsing
                    
                    if ($authResponse.data.token) {
                        Write-Success "Wazuh authentication successful"
                        $wazuhToken = $authResponse.data.token
                        Write-Info "Received token: $($wazuhToken.Substring(0, 20))..."
                        $wazuhStatus = "OK"
                        
                        # Test 5: Get agents
                        Write-Info "Test 5: Fetching agents list..."
                        $headers = @{ Authorization = "Bearer $wazuhToken" }
                        $agentsUrl = "$wazuhUrl/agents?limit=5"
                        $agentsResponse = Invoke-RestMethod -Uri $agentsUrl -Method Get -Headers $headers -UseBasicParsing
                        
                        if ($agentsResponse.data.total_affected_items) {
                            Write-Success "Wazuh API trả về $($agentsResponse.data.total_affected_items) agents"
                        }
                    }
                } catch {
                    Write-Error "Wazuh authentication failed: $($_.Exception.Message)"
                    $wazuhStatus = "AUTH_FAILED"
                    $wazuhError = $_.Exception.Message
                }
            }
        }
    }
}

# =============================================================================
# STEP 3: KIỂM TRA ZABBIX API
# =============================================================================

Write-Section "BƯỚC 3: Kiểm tra Zabbix API"

$zabbixStatus = "UNKNOWN"

if ($config['ZABBIX_ENABLED'] -ne "true") {
    Write-Warning "Zabbix không được enable"
    $zabbixStatus = "DISABLED"
} elseif (-not $config['ZABBIX_API_URL']) {
    Write-Error "ZABBIX_API_URL không được cấu hình"
    $zabbixStatus = "NOT_CONFIGURED"
} else {
    Write-Info "Testing Zabbix API: $($config['ZABBIX_API_URL'])"
    
    try {
        $response = Invoke-WebRequest -Uri $config['ZABBIX_API_URL'] -Method Get -UseBasicParsing
        Write-Success "Zabbix API accessible (HTTP $($response.StatusCode))"
        
        # Test authentication
        $authPayload = @{
            jsonrpc = "2.0"
            method = "user.login"
            params = @{
                user = $config['ZABBIX_API_USER']
                password = $config['ZABBIX_API_PASSWORD']
            }
            id = 1
        } | ConvertTo-Json
        
        $authResponse = Invoke-RestMethod -Uri $config['ZABBIX_API_URL'] -Method Post -Body $authPayload -ContentType "application/json"
        
        if ($authResponse.result) {
            Write-Success "Zabbix authentication successful"
            $zabbixStatus = "OK"
        }
    } catch {
        Write-Error "Zabbix API failed: $($_.Exception.Message)"
        $zabbixStatus = "FAILED"
    }
}

# =============================================================================
# STEP 4: KIỂM TRA BACKEND
# =============================================================================

Write-Section "BƯỚC 4: Kiểm tra Mini-SOC Backend"

$backendRunning = docker ps --format "{{.Names}}" | Select-String "backend"

if ($backendRunning) {
    Write-Success "Backend container đang chạy"
    
    Write-Info "Kiểm tra logs..."
    $logs = docker logs $backendRunning 2>&1 | Select-String -Pattern "wazuh|collector" | Select-Object -Last 10
    
    if ($logs) {
        Write-Info "Recent logs:"
        $logs | ForEach-Object { Write-Host "  $_" }
    }
} else {
    Write-Error "Backend container KHÔNG chạy"
}

# =============================================================================
# STEP 5: KIỂM TRA DATABASE
# =============================================================================

Write-Section "BƯỚC 5: Kiểm tra Database"

$dbContainer = docker ps --format "{{.Names}}" | Select-String "db"

if ($dbContainer) {
    Write-Success "Database container đang chạy"
    
    $wazuhEvents = docker exec $dbContainer psql -U postgres -d mini_soc_prod -tAc "SELECT COUNT(*) FROM wazuh_events;" 2>$null
    $wazuhEvents = $wazuhEvents.Trim()
    
    Write-Info "Wazuh events trong database: $wazuhEvents"
    
    if ([int]$wazuhEvents -gt 0) {
        Write-Success "Database có $wazuhEvents events"
    } else {
        Write-Warning "Database KHÔNG CÓ events"
    }
}

# =============================================================================
# BÁO CÁO
# =============================================================================

Write-Section "BÁO CÁO CHẨN ĐOÁN"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         DIAGNOSTIC SUMMARY                     ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. WAZUH API: $wazuhStatus" -ForegroundColor $(if ($wazuhStatus -eq "OK") { "Green" } else { "Red" })
if ($wazuhStatus -eq "OK") {
    Write-Host "   ✓ Wazuh API hoạt động bình thường" -ForegroundColor Green
} else {
    Write-Host "   ✗ $wazuhError" -ForegroundColor Red
}

Write-Host ""
Write-Host "2. ZABBIX API: $zabbixStatus" -ForegroundColor $(if ($zabbixStatus -in @("OK", "DISABLED")) { "Green" } else { "Yellow" })

Write-Host ""
Write-Host "3. BACKEND: $(if ($backendRunning) { 'RUNNING' } else { 'NOT RUNNING' })"

Write-Host ""
Write-Host "4. DATABASE: $wazuhEvents events"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         KẾT LUẬN                               ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if ($wazuhStatus -eq "OK" -and [int]$wazuhEvents -gt 0) {
    Write-Host "✓ HỆ THỐNG HOẠT ĐỘNG BÌNH THƯỜNG" -ForegroundColor Green
} elseif ($wazuhStatus -ne "OK") {
    Write-Host "✗ LỖI TỪ WAZUH API" -ForegroundColor Red
    Write-Host ""
    Write-Host "GIẢI PHÁP:" -ForegroundColor Yellow
    Write-Host "  - Kiểm tra Wazuh service đang chạy"
    Write-Host "  - Kiểm tra credentials trong .env"
    Write-Host "  - Kiểm tra firewall/network"
} else {
    Write-Host "⚠ WAZUH API OK NHƯNG CHƯA CÓ DỮ LIỆU" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "GIẢI PHÁP:" -ForegroundColor Yellow
    Write-Host "  1. Inject test data:"
    Write-Host "     powershell -ExecutionPolicy Bypass -File Fix-DataFlow.ps1"
    Write-Host "  2. Kiểm tra Wazuh alerts file"
    Write-Host "  3. Kiểm tra collector logs"
}

Write-Host ""
