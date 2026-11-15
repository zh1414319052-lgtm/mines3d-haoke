# Build Android density/crop variants from the preserved generated RGBA master.
# This is asset compilation only: no text, fonts or third-party bitmap material.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$project = Split-Path $PSScriptRoot -Parent
$master = [System.Drawing.Bitmap]::new((Join-Path $project 'art\launcher\mines3d-foreground.png'))
$back = [System.Drawing.Color]::FromArgb(255,15,31,45)
function Export-Launcher([int]$size, [string]$path, [string]$shape) {
    $bitmap = [System.Drawing.Bitmap]::new($size,$size)
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = 'AntiAlias'
    $g.InterpolationMode = 'HighQualityBicubic'
    $g.CompositingQuality = 'HighQuality'
    $g.Clear([System.Drawing.Color]::Transparent)
    $brush = [System.Drawing.SolidBrush]::new($back)
    if ($shape -eq 'round') { $g.FillEllipse($brush,0,0,$size,$size) }
    elseif ($shape -ne 'foreground') { $g.Clear($back) }
    # Android adaptive foreground keeps the complete silhouette inside the safe area.
    $scale = if ($shape -eq 'foreground') {0.84} elseif ($shape -eq 'round') {1.0} else {1.13}
    $span = [single]($size*$scale)
    $offset = [single](($size-$span)/2)
    $g.DrawImage($master,[System.Drawing.RectangleF]::new($offset,$offset,$span,$span))
    $bitmap.Save($path,[System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $brush.Dispose(); $bitmap.Dispose()
}
try {
    foreach ($row in @(@('mdpi',48),@('hdpi',72),@('xhdpi',96),@('xxhdpi',144),@('xxxhdpi',192))) {
        $dir=Join-Path $project ('app\src\main\res\mipmap-'+$row[0])
        Export-Launcher $row[1] (Join-Path $dir 'ic_launcher.png') 'square'
        Export-Launcher $row[1] (Join-Path $dir 'ic_launcher_round.png') 'round'
    }
    $draw=Join-Path $project 'app\src\main\res\drawable-nodpi'
    [System.IO.Directory]::CreateDirectory($draw) | Out-Null
    Export-Launcher 432 (Join-Path $draw 'ic_mine_foreground.png') 'foreground'
    Export-Launcher 512 (Join-Path $project 'art\launcher\mines3d-icon-512.png') 'square'
    Export-Launcher 192 (Join-Path $project 'art\launcher\mines3d-icon-round.png') 'round'
} finally { $master.Dispose() }
