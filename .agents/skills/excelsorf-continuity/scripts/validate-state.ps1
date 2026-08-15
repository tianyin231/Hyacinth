param(
    [int]$RequireFreshMinutes = 0
)

$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $skillRoot 'references\project-state.yaml'

if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw "Project state not found: $statePath"
}

$content = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8
$requiredPatterns = @(
    '(?m)^schema_version:\s+\d+$',
    '(?m)^updated_at:\s+"([^"]+)"$',
    '(?m)^\s+current_phase:\s+"[^"]+"$',
    '(?m)^current_task:$',
    '(?m)^\s+status:\s+"[^"]+"$',
    '(?m)^last_completed:$',
    '(?m)^next_actions:$',
    '(?m)^blockers:$',
    '(?m)^changed_files:$',
    '(?m)^verification:$'
)

foreach ($pattern in $requiredPatterns) {
    if ($content -notmatch $pattern) {
        throw "Project state is missing required pattern: $pattern"
    }
}

$updatedAtMatch = [regex]::Match($content, '(?m)^updated_at:\s+"([^"]+)"$')
$updatedAt = [DateTimeOffset]::Parse($updatedAtMatch.Groups[1].Value)

if ($RequireFreshMinutes -gt 0) {
    $age = [DateTimeOffset]::Now - $updatedAt
    if ($age.TotalMinutes -gt $RequireFreshMinutes) {
        throw ('Project state is stale: {0:N1} minutes old; limit is {1}.' -f $age.TotalMinutes, $RequireFreshMinutes)
    }
}

$sourceMatches = [regex]::Matches(
    $content,
    '(?m)^\s+(canonical_requirements|original_requirements):\s+"([^"]+)"$'
)
foreach ($match in $sourceMatches) {
    $path = $match.Groups[2].Value -replace '\\\\', '\'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Referenced source does not exist: $path"
    }
}

if ($content -match '(?i)\b(TODO|TBD)\b') {
    throw 'Project state contains unresolved TODO/TBD markers.'
}

Write-Output "PASS: project state is valid and updated at $($updatedAt.ToString('o'))."
