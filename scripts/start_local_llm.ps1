$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$modelPath = Join-Path $projectRoot '.private/models/qwen/qwen2.5-1.5b-instruct-q4_k_m.gguf'
$runtimeZip = Join-Path $projectRoot '.private/tools/llama-b7200.zip'
$runtimeDirectory = Join-Path $projectRoot '.private/tools/llama'
if (!(Test-Path -LiteralPath $modelPath) -or !(Test-Path -LiteralPath $runtimeZip)) { throw 'Prepare model and runtime as documented in docs/llm.md' }
if ((Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e') { throw 'Model checksum mismatch' }
if ((Get-FileHash -LiteralPath $runtimeZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne '4c69e78ab94b2d05326f9c066ecf89587420eb3de9809c444cf24cd67c238030') { throw 'Runtime checksum mismatch' }
if (Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 18080 is already in use; existing process left unchanged' }
Expand-Archive -LiteralPath $runtimeZip -DestinationPath $runtimeDirectory -Force
$process = Start-Process -FilePath (Join-Path $runtimeDirectory 'llama-server.exe') -ArgumentList @('-m', ('"' + $modelPath + '"'), '--host', '127.0.0.1', '--port', '18080', '--alias', 'qwen-local', '-c', '2048', '-t', '4', '--parallel', '1', '--log-disable') -WindowStyle Hidden -PassThru
$process.Id | Set-Content (Join-Path $projectRoot '.private/llama-server.pid')
Write-Output 'Local Qwen started on loopback port 18080'
