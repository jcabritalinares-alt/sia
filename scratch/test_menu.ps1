param([int]$Seconds = 3)

Write-Host "Probando Console::KeyAvailable..."
try {
    $hasKey = [Console]::KeyAvailable
    Write-Host "Soportado: $hasKey" -ForegroundColor Green
} catch {
    Write-Host "No disponible en modo no interactivo/redireccionado: $_" -ForegroundColor Yellow
}
