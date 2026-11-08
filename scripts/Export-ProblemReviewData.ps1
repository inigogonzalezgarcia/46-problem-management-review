<#
.SYNOPSIS
    Read-only export of the incidents, problems and changes that problemreview reads, from Jira Service Management Cloud.

.DESCRIPTION
    Only GET requests to the Jira Cloud platform REST API v3: nothing is created, changed, transitioned, commented or deleted, and no
    secret is written to disk.

    Authentication: basic authentication with your Atlassian account email and an API token (id.atlassian.com > Security > API tokens).
    The token is asked for with Get-Credential, kept as a SecureString and only turned into the Authorization header in memory for the
    requests of this session. Use an account that can browse the service project; it needs no admin rights.

    Endpoints:
      - GET /rest/api/3/search/jql with jql, fields, maxResults and nextPageToken. The response has issues, nextPageToken and isLast;
        the script follows nextPageToken until isLast is true. (The older /rest/api/3/search with startAt is deprecated on Jira Cloud.)
      - GET /rest/api/3/field once, to print the custom field ids when -ListFields is given, so you can fill in the parameters below.

    Files:
      - incidents.csv  Issues of type -IncidentType created in the last -Months months (JQL below). Created, resolutiondate, priority,
                       summary, resolution and issuelinks are standard fields; the linked problem is any linked issue whose type is
                       -ProblemType. Service, configuration item, category, team and major incident come from the fields you name
                       (-ServiceField, -CIField, -CategoryField, -TeamField, -MajorIncidentField). With -ReopenCount, the changelog is
                       expanded and every status change out of a done status (-DoneStatuses) counts as a reopen (the changelog
                       returned with a search can be cut short for issues with a long history: read the count as a minimum).
      - problems.csv   Issues of type -ProblemType (all of them, or created in the last -ProblemMonths months). Status, assignee,
                       created, updated, duedate (target date), resolutiondate and summary are standard; the linked change is any
                       linked issue of type -ChangeType. Root cause category, root cause, workaround, known error since, published to
                       the service desk and review date come from the fields you name.
      - changes.csv    Issues of type -ChangeType linked to a problem: status, resolution as the outcome, and the implemented date from
                       -ImplementedField (for example the Actual end field) or, without it, resolutiondate.

    Custom fields of Jira Service Management come back as objects: the script uses value, name, displayName or key, joins lists with
    "; " and turns rich text (Atlassian Document Format) into plain text. Assets object fields come back as object ids in the REST API;
    use a text field for the CI, or export the CIs from Assets and map them in cmdb.csv.

    Not exported by this script: cmdb.csv (Assets or your CMDB: CI, service, criticality, owner team) and settings.json.
    HaloITSM and EasyVista exports with the same columns (see docs/data-format.md) work too: export the incident and problem lists from
    their reporting or list views and rename the columns, or rely on the alternatives problemreview already accepts.

.PARAMETER Site
    Your Jira Cloud site, for example https://fabrikam.atlassian.net.

.PARAMETER Project
    Key of the service project, for example ITSM.

.PARAMETER OutputFolder
    Where the CSV files are written (default .\data).

.PARAMETER Months
    Months of incidents to export (default 6).

.PARAMETER ListFields
    Print the fields of the site (id, name, custom or not) and stop. Run it once to find the custom field ids.

.EXAMPLE
    .\scripts\Export-ProblemReviewData.ps1 -Site https://fabrikam.atlassian.net -Project ITSM -ListFields

.EXAMPLE
    .\scripts\Export-ProblemReviewData.ps1 -Site https://fabrikam.atlassian.net -Project ITSM -OutputFolder .\data `
        -ServiceField customfield_10044 -CIField customfield_10210 -TeamField customfield_10001 -MajorIncidentField customfield_10070 `
        -RootCauseCategoryField customfield_10301 -RootCauseField customfield_10302 -WorkaroundField customfield_10303 `
        -PublishedField customfield_10304 -ReviewDateField customfield_10305 -ImplementedField customfield_10306 -ReopenCount
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $Site,
    [Parameter(Mandatory)] [string] $Project,
    [string] $OutputFolder = '.\data',
    [int] $Months = 6,
    [int] $ProblemMonths = 0,
    [string] $IncidentType = 'Incident',
    [string] $ProblemType = 'Problem',
    [string] $ChangeType = 'Change',
    [string] $ServiceField,
    [string] $CIField,
    [string] $CategoryField = 'components',
    [string] $TeamField,
    [string] $MajorIncidentField,
    [string] $RootCauseCategoryField,
    [string] $RootCauseField,
    [string] $WorkaroundField,
    [string] $KnownErrorSinceField,
    [string] $PublishedField,
    [string] $ReviewDateField,
    [string] $ImplementedField,
    [string[]] $DoneStatuses = @('Resolved', 'Closed', 'Done', 'Completed', 'Canceled'),
    [switch] $ReopenCount,
    [switch] $ListFields
)

$ErrorActionPreference = 'Stop'
$Site = $Site.TrimEnd('/')
$cred = Get-Credential -Message "Atlassian account email and API token for $Site"
$pair = '{0}:{1}' -f $cred.UserName, $cred.GetNetworkCredential().Password
$headers = @{ Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair)); Accept = 'application/json' }
$pair = $null

function Invoke-JiraGet([string] $Path, [hashtable] $Query = @{}) {
    $qs = ($Query.GetEnumerator() | Where-Object { $null -ne $_.Value -and '' -ne $_.Value } |
        ForEach-Object { '{0}={1}' -f $_.Key, [uri]::EscapeDataString([string] $_.Value) }) -join '&'
    $uri = "$Site$Path" + $(if ($qs) { "?$qs" } else { '' })
    Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
}

function Search-Jira([string] $Jql, [string[]] $Fields, [string] $Expand) {
    $token = $null
    do {
        $page = Invoke-JiraGet '/rest/api/3/search/jql' @{ jql = $Jql; fields = ($Fields -join ','); maxResults = 100; nextPageToken = $token; expand = $Expand }
        foreach ($i in $page.issues) { $i }
        $token = $page.nextPageToken
    } while (-not $page.isLast -and $token)
}

function ConvertFrom-Adf($Node) {
    if ($null -eq $Node) { return '' }
    if ($Node -is [string]) { return $Node }
    $text = if ($Node.PSObject.Properties['text']) { $Node.text } else { '' }
    if ($Node.PSObject.Properties['content']) { $text += (@($Node.content | ForEach-Object { ConvertFrom-Adf $_ }) -join ' ') }
    return $text.Trim()
}

function Get-Value($Fields, [string] $Name) {
    if (-not $Name) { return '' }
    $v = $Fields.$Name
    if ($null -eq $v) { return '' }
    $one = {
        param($x)
        if ($x -is [string] -or $x -is [ValueType]) { return [string] $x }
        foreach ($p in 'value', 'name', 'displayName', 'key', 'label', 'objectId') { if ($x.PSObject.Properties[$p]) { return [string] $x.$p } }
        if ($x.PSObject.Properties['type'] -and $x.type -eq 'doc') { return ConvertFrom-Adf $x }
        return [string] $x
    }
    if ($v -is [array]) { return (@($v | ForEach-Object { & $one $_ }) -join '; ') }
    return & $one $v
}

function Get-Links($Issue, [string] $Type) {
    @($Issue.fields.issuelinks | ForEach-Object {
            $o = if ($_.PSObject.Properties['outwardIssue']) { $_.outwardIssue } else { $_.inwardIssue }
            if ($o -and $o.fields.issuetype.name -eq $Type) { $o.key }
        }) -join '; '
}

function Format-Date($Value) {
    # Jira returns 2026-11-02T08:15:00.000+0100; PowerShell 7 may already have turned it into a DateTime
    if (-not $Value) { return '' }
    if ($Value -is [datetime]) { return $Value.ToString('yyyy-MM-dd HH:mm') }
    $s = [string] $Value
    if ($s -match '^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})') { return '{0} {1}' -f $Matches[1], $Matches[2] }
    return $s
}

function Write-Csv([object[]] $Rows, [string] $Name) {
    $path = Join-Path $OutputFolder $Name
    @($Rows) | Export-Csv -Path $path -NoTypeInformation -Encoding utf8
    Write-Host ("{0,7} rows -> {1}" -f @($Rows).Count, $path)
}

if ($ListFields) {
    Invoke-JiraGet '/rest/api/3/field' | Sort-Object custom, name | Format-Table id, name, custom -AutoSize
    return
}

New-Item -ItemType Directory -Force -Path $OutputFolder | Out-Null

# ------------------------------------------------------------------ incidents
$f = @('created', 'resolutiondate', 'priority', 'summary', 'resolution', 'issuelinks') + @($ServiceField, $CIField, $CategoryField, $TeamField, $MajorIncidentField | Where-Object { $_ })
$jql = "project = `"$Project`" AND issuetype = `"$IncidentType`" AND created >= -$($Months * 31)d ORDER BY created ASC"
$incidents = foreach ($i in Search-Jira $jql $f $(if ($ReopenCount) { 'changelog' } else { '' })) {
    $reopen = ''
    if ($ReopenCount -and $i.PSObject.Properties['changelog']) {
        $reopen = @($i.changelog.histories.items | Where-Object { $_.field -eq 'status' -and $DoneStatuses -contains $_.fromString -and $DoneStatuses -notcontains $_.toString }).Count
    }
    $major = Get-Value $i.fields $MajorIncidentField
    [pscustomobject]@{
        'Issue key'          = $i.key
        Created              = Format-Date $i.fields.created
        Resolved             = Format-Date $i.fields.resolutiondate
        Priority             = $i.fields.priority.name
        'Affected services'  = Get-Value $i.fields $ServiceField
        'Configuration item' = Get-Value $i.fields $CIField
        Category             = Get-Value $i.fields $CategoryField
        'Assignment group'   = Get-Value $i.fields $TeamField
        'Linked problem'     = Get-Links $i $ProblemType
        Summary              = $i.fields.summary
        Resolution           = if ($i.fields.resolution) { $i.fields.resolution.name } else { '' }
        'Reopen count'       = $reopen
        'Major incident'     = if ($major -and $major -notin @('No', 'false', 'False')) { 'Yes' } else { 'No' }
    }
}
Write-Csv $incidents 'incidents.csv'

# ------------------------------------------------------------------ problems
$f = @('created', 'status', 'assignee', 'updated', 'duedate', 'resolutiondate', 'summary', 'issuelinks') +
    @($ServiceField, $CIField, $TeamField, $RootCauseCategoryField, $RootCauseField, $WorkaroundField, $KnownErrorSinceField, $PublishedField, $ReviewDateField | Where-Object { $_ })
$jql = "project = `"$Project`" AND issuetype = `"$ProblemType`"" + $(if ($ProblemMonths -gt 0) { " AND created >= -$($ProblemMonths * 31)d" } else { '' }) + ' ORDER BY created ASC'
$changeKeys = @{}
$problems = foreach ($p in Search-Jira $jql $f '') {
    $chg = Get-Links $p $ChangeType
    foreach ($k in ($chg -split '; ' | Where-Object { $_ })) { $changeKeys[$k] = (@($changeKeys[$k]) + $p.key | Where-Object { $_ }) -join '; ' }
    $wa = Get-Value $p.fields $WorkaroundField
    [pscustomobject]@{
        'Issue key'                 = $p.key
        Summary                     = $p.fields.summary
        Created                     = Format-Date $p.fields.created
        Status                      = $p.fields.status.name
        Assignee                    = if ($p.fields.assignee) { $p.fields.assignee.displayName } else { '' }
        'Owner team'                = Get-Value $p.fields $TeamField
        'Affected services'         = Get-Value $p.fields $ServiceField
        'Configuration item'        = Get-Value $p.fields $CIField
        'Root cause category'       = Get-Value $p.fields $RootCauseCategoryField
        'Root cause'                = Get-Value $p.fields $RootCauseField
        Workaround                  = if ($wa) { 'Yes' } else { 'No' }
        'Workaround text'           = $wa
        'Known error since'         = Get-Value $p.fields $KnownErrorSinceField
        'Published to service desk' = Get-Value $p.fields $PublishedField
        'Linked change'             = $chg
        'Target date'               = $p.fields.duedate
        Updated                     = Format-Date $p.fields.updated
        'Review date'               = Get-Value $p.fields $ReviewDateField
        Resolved                    = Format-Date $p.fields.resolutiondate
    }
}
Write-Csv $problems 'problems.csv'

# ------------------------------------------------------------------ changes linked to problems
$changes = @()
$keys = @($changeKeys.Keys | Sort-Object)
for ($n = 0; $n -lt $keys.Count; $n += 50) {
    $chunk = $keys[$n..([Math]::Min($n + 49, $keys.Count - 1))]
    $f = @('summary', 'status', 'resolution', 'resolutiondate') + @($ImplementedField | Where-Object { $_ })
    $changes += foreach ($c in Search-Jira ("key in ({0})" -f ($chunk -join ',')) $f '') {
        $impl = Get-Value $c.fields $ImplementedField
        [pscustomobject]@{
            'Issue key'      = $c.key
            Summary          = $c.fields.summary
            Status           = $c.fields.status.name
            Implemented      = if ($impl) { Format-Date $impl } else { Format-Date $c.fields.resolutiondate }
            'Linked problem' = $changeKeys[$c.key]
            Outcome          = if ($c.fields.resolution) { $c.fields.resolution.name } else { '' }
        }
    }
}
Write-Csv $changes 'changes.csv'

$cred = $null
$headers = $null
Write-Host 'Done. Add cmdb.csv (CI, service, criticality, owner team) and settings.json; see docs/data-format.md.'
