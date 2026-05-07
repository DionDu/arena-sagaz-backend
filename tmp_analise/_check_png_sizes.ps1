Add-Type -AssemblyName System.Drawing
$base = 'C:\desenvolvimento\apps_backup_260429\arena-sagaz\arena-sagaz-backend\tmp_analise\retratos_divergencia'
$pngs = Get-ChildItem $base -Recurse -Filter '*.png' -ErrorAction SilentlyContinue | Select-Object -First 10
foreach ($f in $pngs) {
    $img = [System.Drawing.Image]::FromFile($f.FullName)
    $kind = if ($f.Name -like '*_cnn_*') {'CNN'} elseif ($f.Name -like '*_mm_*') {'MM '} else {'???'}
    Write-Output ("{0} {1,4}x{2,4}  {3}" -f $kind, $img.Width, $img.Height, $f.Name)
    $img.Dispose()
}
