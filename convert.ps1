# VIP 등급수불/에이징 원본 xlsx -> data/raw_grade.csv, data/aging.csv
# 원본은 DRM-free(PK 헤더). Excel COM 으로 Value2 읽어 .NET 으로 UTF-8(BOM) CSV 작성.
# 대시보드는 raw_grade(수불)+aging(에이징) 2개만 쓰고 나머지 지표는 앱이 직접 계산한다.
# NOTE: 실행 문자열은 ASCII-only 유지(PS5.1이 BOM없는 .ps1을 ANSI로 읽어 한글 깨짐).
#       시트는 한글명이 아니라 ASCII 헤더로 탐지(수불 A1='CURR_STD_YM' / 에이징 c1='YM'&c7='MAU').
#       수불·에이징이 한 파일에 있으면 -Src 만 주면 됨(-AgingSrc 생략 시 -Src 재사용).
param(
  [string]$Src = "C:\Users\USER\Desktop\이은지\1. 업무\2. CRM\2. 기존고객\3. VIP\8. DAUMAU 개선\등급수불 및 에이징 raw_2605까지.xlsx",
  [string]$AgingSrc = ""
)
if(-not $AgingSrc){ $AgingSrc = $Src }   # 통합 파일이면 같은 파일에서 에이징 추출
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $here 'data'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir 'raw_grade.csv'

$cols = @('CURR_STD_YM','GRAD_STATUS','GRAD_MOVEMENT','CURR_GRAD_GB',
  'CURR_NLINE_MEM_GRAD_CD','CURR_NLINE_MEM_GRAD_NM','PREV_GRAD_GB',
  'PREV_NLINE_MEM_GRAD_CD','PREV_NLINE_MEM_GRAD_NM','CUST_CNT','MAU','DAU')

function Esc([object]$v){
  if($null -eq $v){ return '' }
  $s = [string]$v
  if($s -match '[",\r\n]'){ '"' + ($s -replace '"','""') + '"' } else { $s }
}

$BOM = New-Object System.Text.UTF8Encoding($true)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  # ── 수불: A1=='CURR_STD_YM' 시트 → raw_grade.csv (12 cols) ──
  $wb = $xl.Workbooks.Open($Src, 0, $true)
  $ws = $null
  foreach($s in $wb.Worksheets){
    if([string]$s.Cells(1,1).Value2 -eq 'CURR_STD_YM'){ $ws = $s; break }
  }
  if($null -eq $ws){ throw "RAW sheet (A1=CURR_STD_YM) not found" }
  $data = $ws.UsedRange.Value2; $rmax = $ws.UsedRange.Rows.Count
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine($cols -join ',')
  $n = 0
  for($i=2; $i -le $rmax; $i++){
    if($null -eq $data[$i,1]){ continue }
    $line = for($j=1; $j -le 12; $j++){
      $v = $data[$i,$j]
      if($j -eq 1 -and ($v -is [double] -or $v -is [int])){ $v = [string][int]$v }
      Esc $v
    }
    [void]$sb.AppendLine(($line -join ','))
    $n++
  }
  [System.IO.File]::WriteAllText($outFile, $sb.ToString(), $BOM)
  Write-Host "WROTE $outFile ($n rows)"
  $wb.Close($false)

  # ── 에이징: 헤더행 c1=='YM' & c7=='MAU' 인 시트 → aging.csv ──
  # 추출 컬럼: YM, GRADE_CD(3), GRADE_NM(4), AGING(5), 유효회원수(6), MAU(7), DAU(8)
  if($AgingSrc -and (Test-Path $AgingSrc)){
    $wb2 = $xl.Workbooks.Open($AgingSrc, 0, $true)
    $aws = $null; $hr = 0
    foreach($s in $wb2.Worksheets){
      $d = $s.UsedRange.Value2; $rm = [Math]::Min($s.UsedRange.Rows.Count, 6)
      for($r=1; $r -le $rm; $r++){
        if([string]$d[$r,1] -eq 'YM' -and [string]$d[$r,7] -eq 'MAU'){ $aws=$s; $hr=$r; break }
      }
      if($aws){ break }
    }
    if($null -eq $aws){ throw "Aging sheet (header YM..MAU) not found" }
    $d = $aws.UsedRange.Value2; $rmax2 = $aws.UsedRange.Rows.Count
    $aCols = @(1,3,4,5,6,7,8)
    $sb2 = New-Object System.Text.StringBuilder
    [void]$sb2.AppendLine('YM,GRADE_CD,GRADE_NM,AGING,EFF_CNT,MAU,DAU')
    $m = 0
    for($i=$hr+1; $i -le $rmax2; $i++){
      $ym = $d[$i,1]
      if($null -eq $ym -or -not ([string]$ym -match '^\d{6}')){ continue }
      $line = foreach($c in $aCols){
        $v = $d[$i,$c]
        if($c -eq 1 -and ($v -is [double] -or $v -is [int])){ $v = [string][int]$v }
        Esc $v
      }
      [void]$sb2.AppendLine(($line -join ','))
      $m++
    }
    $agFile = Join-Path $outDir 'aging.csv'
    [System.IO.File]::WriteAllText($agFile, $sb2.ToString(), $BOM)
    Write-Host "WROTE $agFile ($m rows)"
    $wb2.Close($false)
  }
} finally {
  $xl.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
