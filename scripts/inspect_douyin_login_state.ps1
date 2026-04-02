param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId
)

py -3 -m app.cli.inspect_login_state --account-id $AccountId
