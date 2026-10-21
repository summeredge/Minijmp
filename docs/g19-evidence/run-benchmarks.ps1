$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path "$PSScriptRoot/../..")
$python = "$PWD/.venv/Scripts/python.exe"
$env:PYTHONHASHSEED = '0'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$out = 'docs/g19-evidence'
if (Test-Path "$out/benchmark-complete.txt") {
    Remove-Item -LiteralPath "$out/benchmark-complete.txt"
}

& $python "$out/acceptance.py" *> "$out/gui-acceptance.log"
if ($LASTEXITCODE) { throw 'GUI acceptance failed' }
foreach ($hotspot in 'F01','F11','F02','F04','F06','F08') {
    & $python tools/benchmark_statistics.py $hotspot --output "$out/statistics-$hotspot.json" *> "$out/statistics-$hotspot.log"
    if ($LASTEXITCODE) { throw "Statistics benchmark failed: $hotspot" }
}
& $python tools/benchmark_data_processing.py --output "$out/data" *> "$out/data-benchmark.log"
if ($LASTEXITCODE) { throw 'Data benchmark failed' }
& $python tools/benchmark_g18.py --source-dir docs/g18-evidence/before --output "$out/render-before" --scenario matrix --scenario matrix-orig --scenario matrix-tk --scenario table --scenario spc --scenario excel --scenario series --scenario series-tk --scenario dialog --scenario reports --scenario wide *> "$out/render-before.log"
if ($LASTEXITCODE) { throw 'Before rendering benchmark failed' }
& $python tools/benchmark_g18.py --output "$out/render-current" *> "$out/render-current.log"
if ($LASTEXITCODE) { throw 'Current rendering benchmark failed' }
& $python "$out/supplemental/benchmark.py" --repo "$PWD" --scenarios "$PWD/$out/supplemental-scenarios.json" *> "$out/supplemental.log"
if ($LASTEXITCODE) { throw 'Supplemental benchmark controller failed' }
& $python "$out/summarize_performance.py" *> "$out/performance-summary.log"
if ($LASTEXITCODE) { throw 'Benchmark state, phase or repeat validation failed' }
'Completed' | Set-Content "$out/benchmark-complete.txt"
