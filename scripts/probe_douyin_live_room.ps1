param(
    [Parameter(Mandatory = $true)]
    [string]$RoomId,
    [Parameter(Mandatory = $true)]
    [string]$AccountId,
    [string]$RoomUrl = ""
)

$arguments = @(
    "-3",
    "-m",
    "app.cli.probe_douyin_live_room",
    "--room-id",
    $RoomId,
    "--account-id",
    $AccountId
)

if ($RoomUrl) {
    $arguments += @("--room-url", $RoomUrl)
}

py @arguments
