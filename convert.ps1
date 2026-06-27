# VIP grade-movement source xlsx -> data/*.csv
# Source is NOT DRM (PK header). Read Value2 via Excel COM, write UTF-8(BOM) CSV via .NET.
# NOTE: keep executable strings ASCII-only; PS5.1 may read this .ps1 as ANSI and mangle non-ASCII.
# Tables are located by ASCII header anchors (no Korean sheet-name / Korean-token dependency).
#
# Outputs:
#   raw_grade.csv     - RAW input (A1 = CURR_STD_YM)            [for MAU/DAU pillar + flexibility]
#   monthly_grade.csv - per (YM, grade) movement table          [header c1=YM c2=GRADE]
#   vip_vs_normal.csv - VIP vs normal group compare             [header c1=YM c2=GROUP]
#   conversion.csv    - normal->VIP conversion & internal churn [header c1=YM, none of the others]
#   vip_growth.csv    - VIP net / needed-new scenarios          [header c1=YM, a cell starts 'VIP_']
#   move_matrix.csv   - from->to transition matrix              [header c1=YM c2=FROM_CD]
param(
  [string]$Src = "C:\Users\USER\Desktop\이은지\1. 업무\2. CRM\2. 기존고객\3. VIP\8. DAUMAU 개선\(제휴제외)VIP_등급수불_TEMPLATE_auto_v3_251215.xlsx"
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $here 'data'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Esc([object]$v){
  if($null -eq $v){ return '' }
  $s = [string]$v
  if($s -match '[",\r\n]'){ '"' + ($s -replace '"','""') + '"' } else { $s }
}
function WriteCsv([string]$file, [System.Text.StringBuilder]$sb){
  $utf8bom = New-Object System.Text.UTF8Encoding($true)
  [System.IO.File]::WriteAllText($file, $sb.ToString(), $utf8bom)
}
# Dump a table from a sheet's Value2 grid: header at row hr, ncols wide.
# Emits header + every data row with a non-empty column-1 (skips internal/trailing blanks).
# YM (col 1) forced to int-string so 202501 stays text, not 202,501 / 202501.0.
function DumpTable($data, [int]$hr, [int]$ncols, [int]$rmax, [string]$file){
  $sb = New-Object System.Text.StringBuilder
  # header
  $h = for($j=1; $j -le $ncols; $j++){ Esc $data[$hr,$j] }
  [void]$sb.AppendLine(($h -join ','))
  $n = 0
  for($i=$hr+1; $i -le $rmax; $i++){
    $c1 = $data[$i,1]
    if($null -eq $c1 -or [string]$c1 -eq ''){ continue }
    $line = for($j=1; $j -le $ncols; $j++){
      $v = $data[$i,$j]
      if($j -eq 1 -and ($v -is [double] -or $v -is [int])){ $v = [string][int]$v }
      Esc $v
    }
    [void]$sb.AppendLine(($line -join ','))
    $n++
  }
  WriteCsv $file $sb
  Write-Host ("WROTE {0} ({1} rows)" -f (Split-Path -Leaf $file), $n)
}

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Src, 0, $true)
  foreach($ws in $wb.Worksheets){
    $ur = $ws.UsedRange
    $data = $ur.Value2
    $rmax = $ur.Rows.Count; $cmax = $ur.Columns.Count
    if($null -eq $data){ continue }
    # absolute-position grid: Value2 is 1-based but indexed within UsedRange.
    for($r=1; $r -le [Math]::Min($rmax,60); $r++){
      $c1 = [string]$data[$r,1]
      if($c1 -eq 'CURR_STD_YM'){
        DumpTable $data $r 12 $rmax (Join-Path $outDir 'raw_grade.csv'); break
      }
      if($c1 -eq 'YM'){
        $c2 = if($cmax -ge 2){[string]$data[$r,2]}else{''}
        if($c2 -eq 'GRAD_STATUS' -or $c2 -eq ''){ break }   # FACTS engine / 월목록 -> skip
        if($c2 -eq 'GRADE'){ DumpTable $data $r 12 $rmax (Join-Path $outDir 'monthly_grade.csv'); break }
        elseif($c2 -eq 'GROUP'){ DumpTable $data $r 12 $rmax (Join-Path $outDir 'vip_vs_normal.csv'); break }
        elseif($c2 -eq 'FROM_CD'){ DumpTable $data $r 7 $rmax (Join-Path $outDir 'move_matrix.csv'); break }
        else {
          $hasVipPrefix = $false
          for($j=1; $j -le $cmax; $j++){ if(([string]$data[$r,$j]).StartsWith('VIP_')){ $hasVipPrefix = $true; break } }
          if($hasVipPrefix){ DumpTable $data $r 9 $rmax (Join-Path $outDir 'vip_growth.csv'); break }
          else { DumpTable $data $r 9 $rmax (Join-Path $outDir 'conversion.csv'); break }
        }
      }
    }
  }
  $wb.Close($false)
} finally {
  $xl.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
