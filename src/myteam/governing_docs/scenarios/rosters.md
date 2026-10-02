# Roster Management

Rosters are reusable collections of skills and workflows hosted in a GitHub repository. The roster commands download and refresh managed roster folders under `.myteam/` by default.

## List available rosters

```bash
myteam rosters list
```

Use `--repo owner/repository` to inspect another GitHub repository.

## Download a roster

```bash
myteam rosters download <roster>
```

This installs the roster at `.myteam/<roster>` and records its source metadata. A custom destination may be supplied as a relative path under the managed root:

```bash
myteam rosters download <roster> <destination>
```

Use `--prefix <path>` to select a different relative managed root, and `--repo owner/repository` to select a different source repository.

## Update managed rosters

```bash
myteam rosters update
```

This refreshes every managed roster under the selected root. To update one roster, provide its managed path:

```bash
myteam rosters update <path>
```

Only folder rosters are supported. Existing unrelated folders are not overwritten; a roster downloaded from the same source should be refreshed with `update`.
