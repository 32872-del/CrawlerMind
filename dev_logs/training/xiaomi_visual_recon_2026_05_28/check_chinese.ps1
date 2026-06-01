$jsonFiles = Get-ChildItem 'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28\visual_*.json' | Sort-Object Name
$results = @()
foreach($f in $jsonFiles) {
    $content = Get-Content $f.FullName -Raw -Encoding UTF8
    $hasChinese = $content -match '[一-鿿]'
    $results += [PSCustomObject]@{Name=$f.Name; Size=$f.Length; HasChinese=$hasChinese}
}
$results | Export-Csv -Path 'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28\json_check.csv' -NoTypeInformation -Encoding UTF8
$chineseCount = ($results | Where-Object {$_.HasChinese -eq $true}).Count
Write-Host "Total JSON files: $($results.Count)"
Write-Host "Files with Chinese characters: $chineseCount"
