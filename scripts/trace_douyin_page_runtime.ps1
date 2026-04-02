param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$RoomId,

    [string]$RoomUrl,

    [int]$WaitSeconds = 20,

    [string]$Output,

    [switch]$Headless
)

$command = @(
    "-3",
    "-m",
    "app.cli.trace_douyin_page_runtime",
    "--account-id", $AccountId,
    "--room-id", $RoomId,
    "--wait-seconds", $WaitSeconds
)

if ($RoomUrl) {
    $command += @("--room-url", $RoomUrl)
}

if ($Output) {
    $command += @("--output", $Output)
}

if ($Headless) {
    $command += "--headless"
}

& py @command
