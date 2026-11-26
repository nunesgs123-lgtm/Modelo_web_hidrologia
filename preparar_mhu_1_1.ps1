# Prepara congelamento MHU 1.0 e branch MHU-1.1
# Execute na pasta do projeto:
#   .\preparar_mhu_1_1.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$snap = Join-Path $root "snapshots\MHU_1.0_$stamp"
New-Item -ItemType Directory -Force -Path $snap | Out-Null

$files = @(
  "app.py",
  "requirements.txt",
  "README.md",
  "simulacoes_salvas.json",
  ".streamlit\config.toml"
)

foreach ($f in $files) {
  $src = Join-Path $root $f
  if (Test-Path $src) {
    $dst = Join-Path $snap $f
    $dstDir = Split-Path -Parent $dst
    if (-not (Test-Path $dstDir)) {
      New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    }
    Copy-Item -Path $src -Destination $dst -Force
  }
}

@"
MHU 1.0 - congelamento
Data: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Pasta: $snap
Conteudo: copia integral dos arquivos principais da versao atual antes das evolucoes MHU 1.1.
"@ | Set-Content -Path (Join-Path $snap "README_SNAPSHOT.txt") -Encoding UTF8

Write-Host "Snapshot MHU 1.0 criado em: $snap"

if (Get-Command git -ErrorAction SilentlyContinue) {
  git status -sb
  git checkout -b MHU-1.1
  git add snapshots CHANGELOG.md DIAGNOSTICO_ARQUITETURA_MHU.md preparar_mhu_1_1.ps1 2>$null
  Write-Host "Branch MHU-1.1 criada (ou ja existente). Revise e faca commit se necessario."
} else {
  Write-Host "Git nao encontrado no PATH. Crie a branch manualmente:"
  Write-Host "  git checkout -b MHU-1.1"
}
