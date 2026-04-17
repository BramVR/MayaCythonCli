function Invoke-MayaCythonCompileCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$CliArgs,
        [string]$EnvPath = ""
    )

    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    $py = Get-Command py -ErrorAction SilentlyContinue
    $python = Get-Command python -ErrorAction SilentlyContinue
    $localPython = $null

    if ($EnvPath) {
        $resolvedEnvPath = if ([System.IO.Path]::IsPathRooted($EnvPath)) {
            $EnvPath
        }
        else {
            Join-Path $repoRoot ($EnvPath -replace "/", "\")
        }
        $localPython = Join-Path $resolvedEnvPath "python.exe"
    }

    if ($localPython -and (Test-Path $localPython)) {
        & $localPython -m maya_cython_compile @CliArgs
    }
    elseif ($py) {
        & $py.Source -3 -m maya_cython_compile @CliArgs
    }
    elseif ($python) {
        & $python.Source -m maya_cython_compile @CliArgs
    }
    else {
        throw "No Python interpreter found for CLI wrapper."
    }

    if ($LASTEXITCODE -ne 0) {
        throw ("CLI {0} failed." -f $CliArgs[0])
    }
}
