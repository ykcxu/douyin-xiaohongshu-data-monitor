param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId,
    [Parameter(Mandatory = $true)]
    [string]$RoomUrl
)

py -3 -m app.cli.trace_douyin_live_requests --account-id $AccountId --room-url $RoomUrl
