# Local source data

Keep the original archive and extracted CSVs in this directory for local analysis. The files are intentionally excluded from Git because the synthetic source includes names, addresses, phone numbers, dates of birth, and identifiers that the public project does not need to redistribute.

## Source

- Dataset page: <https://www.misata.studio/datasets/hospital-encounters-claims>
- Direct archive: <https://www.misata.studio/datasets/hospital-encounters-claims.zip>
- License: CC0, as stated on the dataset page and in the archived README. The archive has no separate LICENSE file.
- Retrieved: 2026-11-26T21:22:55Z
- Verified archive SHA-256: `ce8d4d2053ebe0bb1d89e6d5de0d370bbc19d04bcc122c351832916b6591897a`

## Download and extract with PowerShell

Run from the repository root:

```powershell
New-Item -ItemType Directory -Force -Path 'data/raw' | Out-Null
Invoke-WebRequest -Uri 'https://www.misata.studio/datasets/hospital-encounters-claims.zip' -OutFile 'data/raw/hospital-encounters-claims.zip'
Get-FileHash -Algorithm SHA256 -LiteralPath 'data/raw/hospital-encounters-claims.zip'
Expand-Archive -LiteralPath 'data/raw/hospital-encounters-claims.zip' -DestinationPath 'data/raw' -Force
```

Compare the reported hash with the value above. The archive includes the seven CSV tables plus `README.md`, `INTEGRITY.txt`, `RECIPE.json`, and `ANSWERS.sql`. Do not treat the publisher's sample query results as the project's PostgreSQL execution evidence.

See [`docs/dataset_profile.md`](../../docs/dataset_profile.md) for the verified schema, counts, relationships, missingness, dates, and financial semantics.
