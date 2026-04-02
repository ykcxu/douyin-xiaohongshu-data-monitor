param(
    [Parameter(Mandatory = $true)]
    [string]$Input,
    [int]$Top = 20
)

py -3 -m app.cli.analyze_douyin_trace --input $Input --top $Top
