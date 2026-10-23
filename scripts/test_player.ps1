Add-Type -AssemblyName presentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$fullPath = (Resolve-Path 'voice/assets/expressions/expression_sample_1.mp3').Path
$player.Open([System.Uri]$fullPath)
Start-Sleep -Milliseconds 800
Write-Host "Duration:" $player.NaturalDuration.TimeSpan.TotalSeconds "seconds"
$player.Close()
