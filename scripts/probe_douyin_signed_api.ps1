param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [Parameter(Mandatory = $true)]
    [string]$RoomId,

    [string]$RoomUrl,

    [ValidateSet("room-web-enter", "webcast-setting", "user-me")]
    [string]$Preset = "room-web-enter",

    [string]$Output,

    [switch]$Headless
)

$command = @(
    "-3",
    "-m",
    "app.cli.probe_douyin_signed_api",
    "--account-id", $AccountId,
    "--room-id", $RoomId,
    "--preset", $Preset
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
