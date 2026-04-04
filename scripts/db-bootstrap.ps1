$ErrorActionPreference = "Stop"

& "$PSScriptRoot\db-up.ps1"
& "$PSScriptRoot\db-migrate.ps1"
& "$PSScriptRoot\db-seed.ps1"
