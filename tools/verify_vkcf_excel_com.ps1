<#
.SYNOPSIS
  Excel-COM-Gegenprobe fuer eine migrierte Kalkulations-Mappe: echte Neuberechnung, Fehlerwerte je Blatt,
  Wirkung der bedingten Formatierung (DisplayFormat), Versionsmarker.

.DESCRIPTION
  Lauf:  powershell -ExecutionPolicy Bypass -File tools\verify_vkcf_excel_com.ps1 -File <pfad.xlsx> [-CfProbe "Verkauf Cashflow!L18,Verkauf Cashflow!L19"]

  Regeln aus der Fehlerkartei (ERR-2026-09-02-global-excel-com-zweite-instanz-leeres-blatt,
  ERR-2026-09-02-global-openpyxl-cf-fuellung-ohne-bgcolor):
  - eigene, unsichtbare Excel-Instanz; die laufende Instanz des Nutzers wird nie angefasst
  - Workbook UND Worksheet nach dem Oeffnen auf $null pruefen, mit Wiederholung oeffnen
  - Erfolg am Ergebnis messen (Fehlerwerte = 0, CF-Farbe sichtbar), nicht am fehlerfreien Start
  - Datei schreibgeschuetzt oeffnen, nichts speichern, Instanz im finally schliessen und freigeben
  Ausgabe ASCII (Windows-Konsole). Exit 0 = alles bestanden, 1 = Befund, 2 = Excel nicht erreichbar.
#>
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$CfProbe = "",
    [string]$Marker = "AUFTEILER_TPL_V2",
    [int]$Retries = 3
)

$ErrorActionPreference = "Stop"
$fails = New-Object System.Collections.Generic.List[string]
$passes = 0
function Check([string]$label, [bool]$ok, [string]$detail = "") {
    if ($ok) { $script:passes++ } else { $script:fails.Add("$label - $detail") }
}

$full = (Resolve-Path -LiteralPath $File).Path
$excel = $null; $wb = $null
# PIDs vorher merken: die Instanz, die danach neu ist, gehoert diesem Skript und wird am Ende hart beendet,
# falls COM-Release sie nicht schliesst (ERR-2026-09-02: verwaiste unsichtbare Instanzen)
$pidsBefore = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$released = New-Object System.Collections.Generic.List[object]
function Rel($o) { if ($null -ne $o) { $script:released.Add($o) } }
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false
    $excel.EnableEvents = $false

    for ($i = 1; $i -le $Retries -and $null -eq $wb; $i++) {
        try { $wb = $excel.Workbooks.Open($full, 0, $true) } catch { Start-Sleep -Milliseconds 800 }
        if ($null -ne $wb -and $wb.Worksheets.Count -lt 1) { $wb.Close($false); $wb = $null }
    }
    if ($null -eq $wb) { Write-Output "FEHLER: Workbook nach $Retries Versuchen nicht geoeffnet: $full"; exit 2 }

    $excel.CalculateFullRebuild()
    $excel.Calculate()

    # 1. Fehlerwerte je Blatt (ISERROR ueber den benutzten Bereich, per Excel selbst gerechnet)
    $sheets = $wb.Worksheets; Rel $sheets
    foreach ($ws in $sheets) {
        if ($null -eq $ws) { Check "Worksheet-Objekt" $false "null"; continue }
        Rel $ws
        $used = $ws.UsedRange; Rel $used
        if ($null -eq $used) { continue }
        $addr = $used.Address($false, $false)
        $n = $excel.Evaluate("SUMPRODUCT(--ISERROR('" + $ws.Name + "'!" + $addr + "))")
        $count = 0; if ($n -is [double] -or $n -is [int]) { $count = [int]$n }
        $detail = "$count Zellen mit #-Fehler in $addr"
        if ($count -gt 0 -and $count -le 60) {
            # die ersten Fehlerzellen benennen, damit der Befund ohne Excel nachvollziehbar ist
            $hits = New-Object System.Collections.Generic.List[string]
            foreach ($c in $used.Cells) { if ($hits.Count -ge 12) { break }; $v = $c.Value2; if ($v -is [int] -and $v -lt 0 -and $c.Text -like '#*') { $hits.Add($c.Address($false, $false) + '=' + $c.Text) } }
            if ($hits.Count -gt 0) { $detail += " | " + ($hits -join ', ') }
        }
        Check ("Fehlerwerte in '" + $ws.Name + "'") ($count -eq 0) $detail
    }

    # 2. Versionsmarker
    $hasMarker = $false
    $names = $wb.Names; Rel $names
    foreach ($nm in $names) { Rel $nm; if ($nm.Name -eq $Marker) { $hasMarker = $true } }
    Check "Versionsmarker $Marker" $hasMarker "Defined Name fehlt"

    # 3. CF-Wirkung: an jeder Probe-Zelle die angezeigte Farbe lesen (Existenz einer Regel reicht nicht)
    if ($CfProbe -ne "") {
        foreach ($probe in ($CfProbe -split ",")) {
            $p = $probe.Trim(); if ($p -eq "") { continue }
            $parts = $p -split "!"
            $ws = $wb.Worksheets.Item($parts[0]); Rel $ws
            if ($null -eq $ws) { Check "CF-Probe $p" $false "Blatt fehlt"; continue }
            $cell = $ws.Range($parts[1]); Rel $cell
            $df = $cell.DisplayFormat; Rel $df
            $dfi = $df.Interior; Rel $dfi
            $ci = $cell.Interior; Rel $ci
            $color = $dfi.Color
            $plain = $ci.Color
            Check "CF-Probe $p wirkt" ($color -ne $plain -or $dfi.ColorIndex -ne -4142) ("DisplayFormat=$color Interior=$plain")
        }
    }
}
catch {
    Write-Output ("FEHLER: " + $_.Exception.Message); exit 2
}
finally {
    if ($null -ne $wb) { try { $wb.Close($false) } catch {} }
    if ($null -ne $excel) { try { $excel.Quit() } catch {} }
    foreach ($o in $released) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($o) } catch {} }
    foreach ($o in @($wb, $excel)) { if ($null -ne $o) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($o) } catch {} } }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers(); [GC]::Collect()
    Start-Sleep -Milliseconds 500
    # Erfolg am Ergebnis messen: eine nach dem Start neu erschienene, unsichtbare Instanz ist unsere - hart beenden
    foreach ($x in @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue)) {
        if ($pidsBefore -notcontains $x.Id -and $x.MainWindowHandle -eq 0) { Stop-Process -Id $x.Id -Force -Confirm:$false; Write-Output ("Hinweis: verwaiste Excel-Instanz PID " + $x.Id + " beendet") }
    }
}

Write-Output ("{0} Pruefungen bestanden, {1} fehlgeschlagen" -f $passes, $fails.Count)
foreach ($f in $fails) { Write-Output ("  FAIL: " + $f) }
if ($fails.Count -gt 0) { exit 1 } else { exit 0 }
