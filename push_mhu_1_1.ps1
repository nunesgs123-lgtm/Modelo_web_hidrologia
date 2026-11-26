# Commit e push MHU 1.1 para atualizar o Streamlit Cloud (main)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Branch atual:" (git branch --show-current)
git status -sb

git add -- app.py CHANGELOG.md DIAGNOSTICO_ARQUITETURA_MHU.md preparar_mhu_1_1.ps1 snapshots
if (Test-Path push_mhu_1_1.ps1) { git add -- push_mhu_1_1.ps1 }

git commit -m @"
Atualiza precipitacao e discretizacao temporal (MHU 1.1).

Separa intervalo de registro do passo de integracao, t=0 como CI, recessao e unidades mm/mm-h com compatibilidade de saves antigos.
"@

if ($LASTEXITCODE -ne 0) {
  Write-Host "Commit nao criado (talvez nada a commitar). Continuando com push se houver commits a frente..."
}

git push -u origin HEAD:MHU-1.1
git push origin HEAD:main

Write-Host "`nStatus final:"
git status -sb
git log -2 --oneline
Write-Host "`nPronto. No Streamlit Cloud, aguarde o redeploy ou use Manage app > Reboot."
