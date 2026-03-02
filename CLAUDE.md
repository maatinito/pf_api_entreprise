# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**pf_api_entreprise** is a Go microservice that serves French Polynesian business/establishment data from a CSV file (`exportrte.csv`) over HTTP. It replaces the unstable external `i-taiete` API (`api.gov.pf`) used by the `mes-demarches` Rails application. The JSON response format must be strictly compatible with the original i-taiete API so the Rails `PfEtablissementAdapter` remains unmodified.

The full specification is in `SPEC_PF_ENTREPRISE_SERVICE.md` — always consult it for detailed field mappings, reference tables, and edge cases.

## Build & Run Commands

```bash
# Initialize module (first time only)
go mod init github.com/govpf/pf-entreprise

# Build
go build -o pf-entreprise .

# Run (CSV must exist at CSV_PATH)
CSV_PATH=./exportrte.csv PORT=3000 ./pf-entreprise

# Run tests
go test ./...

# Run a single test
go test -run TestFunctionName ./...

# Run tests with verbose output
go test -v ./...

# Run tests with coverage
go test -cover ./...

# Docker build
docker build -t govpf/pf-entreprise .
```

## Architecture

### Design Constraints

- **Zero external dependencies** — stdlib only, except `golang.org/x/text/encoding/charmap` for Windows-1252 CSV decoding
- **In-memory index** — the entire CSV (~115K rows) is loaded into a `map[string][]Etablissement` keyed by `Numtah` (6-char TAHITI number)
- **Atomic reload** — CSV reloads use `sync.RWMutex` so in-flight requests keep serving old data until the new index is ready
- **Performance targets** — response < 10ms, RAM < 100MB, Docker image < 30MB

### Planned File Layout

| File | Purpose |
|------|---------|
| `main.go` | HTTP server, routing, startup |
| `csv.go` | CSV parsing, encoding detection, index construction |
| `models.go` | Go structs matching the i-taiete JSON output |
| `reference.go` | Reference table lookups (effectifs, formes juridiques, NAF codes, communes/subdivisions) |
| `handlers.go` | HTTP handlers for all endpoints |
| `reference_data/` | Embedded JSON files for reference tables (NAF, formes juridiques, effectifs, communes) |
| `main_test.go` | Tests |
| `Dockerfile` | Multi-stage build (golang:1.23-alpine → alpine:3.19) |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/etablissements/Entreprise?numeroTahiti={XXXXXX}` | GET | Main endpoint — returns JSON array of establishments |
| `/healthz` | GET | Health check — returns 200 when CSV loaded, 503 during loading |
| `/admin/reload` | POST | Hot-reload CSV without restart |

### Key Implementation Rules

- Empty CSV fields → `null` in JSON (never empty string `""`)
- ADRGEO containing literal `""` → treat as empty → `null`
- Dates convert from `DD/MM/YYYY` → `YYYY-MM-DD`; empty → `null`
- `NumETA` "001" → integer `1` in JSON
- The service returns ALL establishments including radiated ones (filtering is done Rails-side)
- Unknown `code_Fjur` values must log a WARNING (not fail)
- Preserve trailing spaces in `raisonSociale` and `nomCommercial`

### Data Source

The CSV file `exportrte.csv` is published on data.gouv.fr and can be downloaded with:
```bash
curl -L -o exportrte.csv "https://www.data.gouv.fr/api/1/datasets/r/34184a7f-a4bf-4cf3-ac36-531388f3a6cb"
```

### Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3000` | HTTP listen port |
| `CSV_PATH` | `/data/exportrte.csv` | Path to the CSV file |
| `LOG_LEVEL` | `info` | Log level (debug, info, warn) |

## Language

The spec, commit messages, and code comments are in French. Variable names and Go code use English.
