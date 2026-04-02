param(
    [Parameter(Mandatory = $true)]
    [string]$Input,

    [string]$Output
)

$command = @(
    "-3",
    "-m",
    "app.cli.inspect_douyin_frontier_frames",
    "--input", $Input
)

if ($Output) {
    $command += @("--output", $Output)
}

& py @command
