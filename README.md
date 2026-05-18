# EPO Patent Data Pipeline

Downloads EP full-text patents from the [EPO Bulk Data Delivery Service (BDDS)](https://www.epo.org/en/searching-for-patents/data/bulk-data-sets), stores patent metadata in a Neo4j graph database, and stores full-text fields (abstract, description, claims) in PostgreSQL for search and downstream ML/RAG workflows.

---

## Architecture

```
EPO BDDS API  (product 32 — EP full text)
      │
      ▼
┌─────────────────────────────────┐
│  [1] Downloader                 │── _manifest.csv  (resume state)
│  epo_bdds_full_text_downloader  │
│                                 │
│  · fetches delivery archive     │
│    metadata from API            │
│  · streams & validates ZIPs /   │
│    TARs atomically              │
│  · filters to EP XMLs only      │
└──────────────┬──────────────────┘
               │  filtered archives (.zip / .tar.gz)
               ▼
          data/final/
               │
     ┌─────────┴───────────┐
     │                     │
     ▼                     ▼
┌──────────────┐   ┌───────────────────────┐
│ [2] Graph    │   │ [3] Postgres          │
│ CSV Export   │   │ Full-text Export      │
│              │   │                       │
│ 10 CSVs:     │   │ Extracts:             │
│ publications,│   │ · abstract            │
│ applications,│   │ · description         │
│ IPC/CPC,     │   │ · claims (text+JSON)  │
│ persons,     │   │                       │
│ citations,   │   │ Upserts into:         │
│ relationships│   │ patent_fulltext table │
│              │   │                       │
│ SQLite ckpt  │   │ text-file checkpoint  │
└──────┬───────┘   └───────────┬───────────┘
       │                       │
       ▼                       ▼
┌──────────────┐   ┌───────────────────────┐
│ [4] Neo4j    │   │   PostgreSQL          │
│ Loader       │   │                       │
│              │   │  Ready for full-text  │
│ initial:     │   │  search, embedding,   │
│   bulk MERGE │   │  RAG pipelines        │
│ weekly:      │   └───────────────────────┘
│   incremental│
│   by source  │
│   SQLite ckpt│
└──────┬───────┘
       │
       ▼
   Neo4j DB
  (patent graph —
   publications,
   applications,
   inventors,
   applicants,
   classifications,
   citations)
```

Each stage is independently resumable: re-running picks up exactly where it left off.

---

## Prerequisites

- Python 3.12+
- Docker and Docker Compose (for the databases)

---

## Setup & Quickstart

### 1. Configure environment

```bash
cp .env.example .env
# Open .env and set secure passwords for POSTGRES_PASSWORD and NEO4J_PASSWORD
```

### 2. Start databases

```bash
docker compose up -d
# PostgreSQL: localhost:5432
# Neo4j browser: http://localhost:7474  (bolt: localhost:7687)
```

Wait for both services to become healthy:

```bash
docker compose ps
```

### 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the initial load

Downloads all available EP full-text archives, exports to Neo4j and PostgreSQL:

```bash
bash scripts/initial_load.sh
```

Logs are written to `logs/initial_load.log` and `logs/pipeline_<timestamp>.log`.

> **Note:** The initial download is large (hundreds of GBs). The pipeline is resumable — if it is interrupted, re-run the same script and it will skip already-completed work.

---

## Weekly Automated Updates

The `scripts/weekly_run.sh` script downloads newly published data and incrementally updates both databases.

### Set up cron (Linux)

```bash
crontab -e
```

Add the following line (runs every Monday at 02:00):

```
0 2 * * 1 /absolute/path/to/epo-patent-data-pipeline/scripts/weekly_run.sh
```

Replace `/absolute/path/to/epo-patent-data-pipeline` with the actual path on your system.

Weekly run logs are appended to `logs/cron.log`.

---

## Running Tests

No external services required — all tests are unit tests using in-memory SQLite, temp files, and mocked drivers.

```bash
pytest -v
```

Expected output: 59 tests, all passing, in under 10 seconds.

---

## Module Reference

All modules are run from the project root with `PYTHONPATH=src` set (handled automatically by the orchestrator and shell scripts).

### Orchestrator (recommended entry point)

```bash
python -m orchestrator.cli --mode initial   # first-time full load
python -m orchestrator.cli --mode weekly    # incremental update
```

Runs all four stages in sequence, with unified logging.

---

### [1] Downloader

```bash
cd src/epo_bdds_full_text_downloader
python main.py [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--final-dir PATH` | `/mnt/d/epo_data/epo_fulltext_clean` | Where to store filtered archives |
| `--raw-dir PATH` | `/tmp/epo_tmp_download` | Temporary raw download directory |
| `--staging-dir PATH` | `/tmp/epo_clean_staging` | Temporary filtered staging directory |
| `--manifest-path PATH` | `<final-dir>/_manifest.csv` | Resume manifest |
| `--xml-prefix PREFIX` | `ep` | Keep only XMLs whose basename starts with this |
| `-v` | — | Increase verbosity (`-v` = INFO, `-vv` = DEBUG) |

---

### [2] Graph CSV Export

```bash
python -m epo_bdds_full_text_graph_export.cli \
  --archives-dir data/final \
  --output-dir data/graph_output
```

| Flag | Description |
|------|-------------|
| `--archives-dir PATH` | Directory of BDDS delivery archives (mutually exclusive with `--xml-dir`) |
| `--xml-dir PATH` | Directory of pre-extracted XML files |
| `--output-dir PATH` | Where to write the 10 CSVs and SQLite checkpoint |
| `--stop-after N` | Stop after N XMLs (for testing) |
| `--fail-fast` | Abort on first error instead of continuing |

Output CSVs in `--output-dir`:

| File | Contents |
|------|----------|
| `nodes_publication.csv` | pub_id, country, pub_number, kind_code, date, language |
| `nodes_application.csv` | appln_id, filing date, gazette info |
| `nodes_ipc_classification.csv` | IPC codes |
| `nodes_cpc_classification.csv` | CPC codes |
| `nodes_applicant.csv` | Applicant organisations |
| `nodes_inventor.csv` | Inventors |
| `nodes_attorney_representative.csv` | Attorneys |
| `nodes_citations.csv` | Patent citations |
| `nodes_source_files.csv` | Source XML file references |
| `relationships.csv` | All edges (from_label, rel_type, to_label) |

---

### [3] PostgreSQL Full-text Export

```bash
python -m epo_bdds_full_text_postgres_export.cli \
  --archives-dir data/final \
  --checkpoint data/checkpoints/postgres_fulltext_checkpoint.txt
```

Requires `Patents_PG_DSN` set in `.env`.

| Flag | Default | Description |
|------|---------|-------------|
| `--archives-dir PATH` | — | BDDS delivery archives (mutually exclusive with `--xml-dir`) |
| `--xml-dir PATH` | — | Pre-extracted XML files |
| `--checkpoint PATH` | `data/checkpoints/postgres_fulltext_checkpoint.txt` | Resume checkpoint |
| `--languages LANGS` | `en` | Comma-separated language codes to extract (e.g. `en,de,fr`) |
| `--commit-every N` | `200` | Batch commit size |

Target table: `patent_fulltext (pub_id, lang, abstract_text, description_text, claims_text, claims_json)`.

---

### [4] Neo4j Loader

```bash
# Initial bulk load
python -m neo4j_loader.cli --mode initial --csv-dir data/graph_output

# Weekly incremental update
python -m neo4j_loader.cli --mode incremental --csv-dir data/graph_output
```

Requires `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` set in `.env`.

| Flag | Default | Description |
|------|---------|-------------|
| `--mode initial\|incremental` | `initial` | Bulk load or incremental by source_id |
| `--csv-dir PATH` | `data/graph_output` | Directory containing graph-export CSVs |
| `--step schema\|nodes\|relationships\|all` | `all` | Run a specific step only (initial mode) |
| `--batch-size N` | `500` | Rows per Neo4j transaction |
| `--checkpoint-db PATH` | `data/checkpoints/neo4j_loader_checkpoint.sqlite` | Incremental resume state |

---

## Data Directories

```
data/
  raw/            # raw BDDS download archives (temp, cleaned up after filtering)
  staging/        # filtered staging archives (temp)
  final/          # final filtered archives — input to export stages
  graph_output/   # Neo4j CSV export + SQLite checkpoint
  checkpoints/    # postgres and neo4j loader resume checkpoints
logs/
  pipeline_<timestamp>.log   # per-run orchestrator log
  initial_load.log           # initial load output
  cron.log                   # weekly cron output (appended)
```
