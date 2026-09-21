$path = $PSScriptRoot
Set-Location $path

# Limpiar túnel activo previo
if (Test-Path "$path\.active_tunnel") { Remove-Item "$path\.active_tunnel" }

$logFile = "$env:TEMP\cloudflared_log.txt"
if (Test-Path $logFile) { Remove-Item $logFile }

# Esperar 2 segundos para asegurar que Django esté escuchando en el puerto 8000
Start-Sleep -Seconds 2

$process = Start-Process "cloudflared" -ArgumentList "tunnel", "--url", "http://127.0.0.1:8000" -RedirectStandardError $logFile -NoNewWindow -PassThru

Write-Host "Iniciando túnel de Cloudflare y esperando la URL..." -ForegroundColor Cyan

$url = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logFile) {
        $content = Get-Content $logFile -Raw
        if ($content -match 'https://[a-zA-Z0-9\-]+\.trycloudflare\.com') {
            $url = $Matches[0]
            Set-Content -Path "$path\.active_tunnel" -Value $url
            break
        }
    }
}

if ($url) {
    $targetUrl = "$url/login"
    Write-Host "¡Túnel abierto! Abriendo navegador en: $targetUrl" -ForegroundColor Green
    Start-Process $targetUrl

    # --- CONFIGURACIÓN DE CORREO SMTP DESDE .ENV ---
    $envFile = "$path\.env"
    $envVars = @{}
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $parts = $line.Split("=", 2)
                $envVars[$parts[0].Trim()] = $parts[1].Trim()
            }
        }
    }

    $smtpServer = "smtp.gmail.com"
    $smtpPort = 587
    $usuarioCorreo = if ($envVars["EMAIL_HOST_USER"]) { $envVars["EMAIL_HOST_USER"] } else { "jcabritalinares@gmail.com" }
    $passwordApp = $envVars["EMAIL_HOST_PASSWORD"]
    $destinatario = $usuarioCorreo

    if (-not $passwordApp) {
        Write-Host "No se encontró EMAIL_HOST_PASSWORD en .env, omitiendo envío de correo." -ForegroundColor Yellow
    } else {
        $asunto = "🚀 Nuevo Link de Cloudflare - Inventario"
        $cuerpo = "El enlace de acceso al sistema es: $targetUrl"

        try {
            $mensaje = New-Object System.Net.Mail.MailMessage
            $mensaje.From = New-Object System.Net.Mail.MailAddress($usuarioCorreo)
            $mensaje.To.Add($destinatario)
            $mensaje.Subject = $asunto
            $mensaje.Body = $cuerpo
            $mensaje.IsBodyHtml = $false

            $clienteSmtp = New-Object System.Net.Mail.SmtpClient($smtpServer, $smtpPort)
            $clienteSmtp.EnableSsl = $true
            $clienteSmtp.Credentials = New-Object System.Net.NetworkCredential($usuarioCorreo, $passwordApp)
            
            $clienteSmtp.Send($mensaje)
            Write-Host "¡Correo enviado con éxito a $destinatario!" -ForegroundColor Green
        } catch {
            Write-Host "Error al enviar el correo: $_" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "No se pudo detectar la URL de Cloudflare automáticamente." -ForegroundColor Yellow
    Write-Host "Abriendo acceso local en el navegador: http://localhost:8000/login" -ForegroundColor Cyan
    Start-Process "http://localhost:8000/login"
}

Wait-Process -Id $process.Id