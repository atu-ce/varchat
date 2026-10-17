# Uzun süren ölçüm koşularını (b06 üretim, b07 sadakat) terminalden bağımsız, arka planda başlatır.
# Kullanım (PowerShell, proje kökünde):  .\degerlendirme\gece_kos.ps1 [model]
# Çıktı günlüğü: degerlendirme\sonuclar\gece_<tarih>.log  — betikler kaldığı yerden devam eder, tekrar çalıştırmak güvenlidir.
param([string]$Model = "")
$kok = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $kok ".venv\Scripts\python.exe"
$log = Join-Path $kok ("degerlendirme\sonuclar\gece_" + (Get-Date -Format "yyyy-MM-dd_HHmm") + ".log")
$env:PYTHONIOENCODING = "utf-8"
$args1 = @("degerlendirme\b06_toplu_uret.py"); if ($Model) { $args1 += $Model }
# b07'ye model adı açıkça verilir: başka bir modelin daha yeni üretim dosyası yanlışlıkla yargılanmasın
$args2 = @("degerlendirme\b07_sadakat.py"); if ($Model) { $args2 += @("--model", $Model) }
$komut = "& '$py' " + ($args1 -join " ") + " *>> '$log'; & '$py' " + ($args2 -join " ") + " *>> '$log'"
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-Command", $komut) -WorkingDirectory $kok
Write-Host "Başlatıldı (arka plan). Günlük: $log"
