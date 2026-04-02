param(
    [Parameter(Mandatory = $true)]
    [string]$Input,

    [string]$Output
)

$command = @(
    "-3",
    "-m",
    "app.cli.extract_douyin_frontier_ws",
    "--input", $Input
)

if ($Output) {
    $command += @("--output", $Output)
}

& py @command
