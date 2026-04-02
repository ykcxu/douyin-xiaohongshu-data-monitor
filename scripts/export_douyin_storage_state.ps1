param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId,
    [string]$Operator = ""
)

$arguments = @(
    "-3",
    "-m",
    "app.cli.export_douyin_storage_state",
    "--account-id",
    $AccountId
)

if ($Operator) {
    $arguments += @("--operator", $Operator)
}

py @arguments
