param(
    [string]$Backup = '.private/alfa_course_hackathon.backup',
    [string]$Container = 'hac-audit-20261112'
)
$ErrorActionPreference = 'Stop'
if ($Container -notmatch '^hac-audit-[a-zA-Z0-9-]+$') { throw 'Use a dedicated hac-audit-* container name' }
$archivePath = (Resolve-Path -LiteralPath $Backup).Path
$archiveInfo = Get-Item -LiteralPath $archivePath
if ($archiveInfo.Length -lt 20) { throw 'Archive is too small' }
$archiveStream = [System.IO.File]::OpenRead($archivePath)
try { $magic = New-Object byte[] 5; [void]$archiveStream.Read($magic,0,5) } finally { $archiveStream.Dispose() }
if ([System.Text.Encoding]::ASCII.GetString($magic) -ne 'PGDMP') { throw 'Expected a custom PostgreSQL archive' }
docker inspect $Container *> $null
if ($LASTEXITCODE -eq 0) { throw 'Container already exists. Inspect it or choose a new name; nothing has been removed.' }
$image='postgres:18@sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722'
docker run -d --name $Container --label project=hackandchange --label purpose=private-data-audit --network none --mount "type=bind,source=$archivePath,target=/input/source.backup,readonly" --tmpfs /var/lib/postgresql:rw,size=768m -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=hac_audit $image
if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated audit database' }
$databaseReady=$false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    docker exec $Container pg_isready -U postgres -d hac_audit *> $null
    if ($LASTEXITCODE -eq 0) { $databaseReady=$true; break }
    Start-Sleep -Seconds 1
}
if (-not $databaseReady) { throw 'Audit database did not become ready' }
docker exec $Container pg_restore --exit-on-error --single-transaction --no-owner --no-privileges -U postgres -d hac_audit /input/source.backup
if ($LASTEXITCODE -ne 0) { throw 'Restore failed. Container is retained for inspection.' }
Write-Output "Restored into isolated container $Container. No application database was modified."
