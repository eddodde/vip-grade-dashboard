# VIP 등급수불 원본 xlsx -> data/raw_grade.csv (RAW_입력 시트만)
# 원본은 DRM-free(PK 헤더). Excel COM 으로 Value2 읽어 .NET 으로 UTF-8(BOM) CSV 작성.
# 대시보드는 이 raw 1개 파일만 쓰고 나머지 지표는 앱(app.py)이 직접 계산한다.
# NOTE: 실행 문자열은 ASCII-only 유지(PS5.1이 BOM없는 .ps1을 ANSI로 읽어 한글 깨짐).
#       시트는 한글명이 아니라 A1=='CURR_STD_YM' 헤더로 탐지. -Src 는 호출 시 직접 전달 권장.
param(
  [string]$Src = "C:\Users\USER\Desktop\이은지\1. 업무\2. CRM\2. 기존고객\3. VIP\8. DAUMAU 개선\(제휴제외)VIP_등급수불_TEMPLATE_auto_v3_251215.xlsx"
)
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

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Src, 0, $true)
  $ws = $null
  foreach($s in $wb.Worksheets){
    if([string]$s.Cells(1,1).Value2 -eq 'CURR_STD_YM'){ $ws = $s; break }
  }
  if($null -eq $ws){ throw "RAW sheet (A1=CURR_STD_YM) not found" }
  $ur = $ws.UsedRange
  $data = $ur.Value2
  $rmax = $ur.Rows.Count
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
  [System.IO.File]::WriteAllText($outFile, $sb.ToString(),
    (New-Object System.Text.UTF8Encoding($true)))
  Write-Host "WROTE $outFile ($n rows)"
  $wb.Close($false)
} finally {
  $xl.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
