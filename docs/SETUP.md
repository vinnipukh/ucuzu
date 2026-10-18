# Setup Guide: from CSVs to a running ucuzu

A start-to-finish walkthrough for a new machine. It covers installing the app, building the SQLite database from the committed CSVs and pulling new CSVs from the upstream data repository [`urazkagangunes/InflationResearchStudy`](https://github.com/urazkagangunes/InflationResearchStudy). Command details and options stay in their owning docs: [GETTING-STARTED.md](GETTING-STARTED.md) (install, run, verify), [DATABASE.md](DATABASE.md) (build pipeline) and [DATA_CONTRACT.md](DATA_CONTRACT.md) (data layout).

```text
InflationResearchStudy (upstream)        this repository                      running app
InflationItems/Datas/  ──copy new──▶  data/raw/        ─┐
Inflations/Datas/      ──copy new──▶  data/inflation/   ├─ build_database.py ─▶ data/prices.db ─▶ Falcon API :8000 ─▶ SvelteKit SPA :5173
(mirror only)                         data/prices_json/ ─┘
```

The CSVs are committed to this repository, so a fresh clone can build the database without visiting upstream. Section 4 is only needed to bring in newer scrapes.

## 1. Prerequisites

- Python ≥ 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js 24 (≥ 22.12) with npm
- Git
- About 10 GB free disk: about 6 GB of data, about 1.5 GB for the database and its build scratch files, plus a temporary upstream clone if you do section 4

## 2. Install

```bash
git clone https://github.com/vinnipukh/cimri-clone.git
cd cimri-clone
uv sync --extra dev
cd frontend && npm install && cd ..
```

## 3. Build the database from the committed CSVs

```bash
uv run python scripts/data_files.py join     # rebuild files committed as .partNNN chunks
uv run python scripts/build_database.py      # writes data/prices.db
```

What the build does (full pipeline: [DATABASE.md](DATABASE.md#build-pipeline)):

1. Joins split files (`join` again, so the first command is optional).
2. Reads every dated CSV under `data/raw/` in parallel. The folder path gives the retailer (`01_Food/Migros/…` → `Markets / Migros`); the file name gives the date. Files without a full date in the name are skipped.
3. Fills in retailers that have no raw CSVs from `data/prices_json/`.
4. Writes the tables, then the price-comparison columns the shop needs (`name_key`, `previous_price`, `price_since`, `is_current`), indexes and views.
5. Swaps the finished file in atomically, so a failed build never leaves a half-written `data/prices.db`.

It takes about 5 minutes on an 8-core machine and ends with a summary line like:

```text
Built …/data/prices.db (1,518 MB): 199 retailers, 928,649 products, 33,551,148 observations in 270s
```

Above that line it prints how many files were skipped, by reason. A large count for `no price column` or `undated or unlabelled` usually means a scraper changed its output; see [Raw CSV ingestion](DATABASE.md#raw-csv-ingestion) for the accepted folder names, date formats and column aliases.

Notes:

- **Rebuild after every data change.** The database is never committed (`*.db` is in `.gitignore`).
- **Windows:** stop the API first. Windows cannot replace a database file that is open.
- **Build somewhere else:** `--db-path path/to/other.db`, then start the API with `PRICES_DB_PATH=path/to/other.db`.
- **An older database** (built before the shop existed) still serves `/analiz`, but the shop's `/api/catalog/*` routes answer 503 `database_outdated` until you rebuild.

## 4. Take new CSVs from InflationResearchStudy

Upstream is large (about 1.3 GB of history; on 2026-10-18 `InflationItems/Datas/` held 10,183 files, 3.4 GB). A partial, sparse, shallow clone downloads only the two data folders.

### 4.1 Where upstream folders go

| Upstream path | Here | Used by |
|---|---|---|
| `InflationItems/Datas/<NN_Group>/…` | `data/raw/<NN_Group>/…` | the database build |
| `Inflations/Datas/<NN_Group>/…` | `data/inflation/<NN_Group>/…` | reference only; the API reads just `data/inflation/EpeyKatfg/monthly_inflation.csv` |
| — | `data/prices_json/`, `data/raw/EpeyKatfg/`, `data/inflation/EpeyKatfg/` | come from the mirror [`vinnipukh/inflationstudymirror`](https://github.com/vinnipukh/inflationstudymirror), not upstream; leave them alone |

When a file exists both here and upstream, **keep the copy here**: it may come from the mirror, which wins on conflicts ([DATA_CONTRACT.md](DATA_CONTRACT.md#ownership)). So the import adds new files only and never overwrites.

### 4.2 Clone the data folders

Run this next to the repository (not inside it):

```bash
cd ..
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/urazkagangunes/InflationResearchStudy.git
cd InflationResearchStudy
git sparse-checkout set --cone InflationItems/Datas Inflations/Datas
git -c core.protectNTFS=false checkout
git log -1 --format='%H %cs'        # note this commit for the commit message
cd ../cimri-clone
```

- `--filter=blob:none` and the sparse checkout download only the files you check out; `--depth 1` skips history.
- `core.protectNTFS=false` is needed on Windows: some upstream file names contain a backslash (for example `Taxi/Datas\taxi_prices_9-7.csv`), which Git for Windows otherwise refuses with `error: invalid path`. With the flag, the backslash becomes a folder (`Taxi/Datas/taxi_prices_9-7.csv`), which is the import rule in [DATA_CONTRACT.md](DATA_CONTRACT.md#rules-for-committed-data). It is harmless on Linux and macOS.
- Use cone-mode paths without a leading `/`. In Git Bash a leading `/` is rewritten into a Windows path (`C:/Program Files/Git/...`) and the sparse checkout comes out empty.

To refresh later: `git -C ../InflationResearchStudy pull --depth 1`, then repeat 4.3.

### 4.3 Copy new files only

Git Bash, Linux or macOS (`-n` = never overwrite):

```bash
cp -rn ../InflationResearchStudy/InflationItems/Datas/. data/raw/
cp -rn ../InflationResearchStudy/Inflations/Datas/. data/inflation/
```

PowerShell (`/XC /XN /XO` = skip files that already exist):

```powershell
robocopy ..\InflationResearchStudy\InflationItems\Datas data\raw /E /XC /XN /XO
robocopy ..\InflationResearchStudy\Inflations\Datas data\inflation /E /XC /XN /XO
```

See what arrived:

```bash
git status --short data/ | wc -l          # new or changed files
git status --short data/ | head -20
```

`git status` should list only new (`??`) files. A modified (`M`) file means something overwrote an existing one; restore it with `git checkout -- <path>`.

### 4.4 Check file sizes

No committed file may exceed 85 MB:

```bash
uv run python scripts/data_files.py check    # exit 1 lists oversized files
uv run python scripts/data_files.py split    # commit them as 80 MB .partNNN chunks instead
```

`split` keeps the original on disk and lists it in the managed block of `.gitignore`; `join` (and the build) rebuild it. Details: [Large files](DATA_CONTRACT.md#large-files-scriptsdata_filespy).

### 4.5 Rebuild and check

```bash
uv run python scripts/build_database.py
uv run pytest
uv run python scripts/verify_falcon_api.py
```

Compare the build summary with the previous one: retailer and product counts should grow, and the skip counts should not jump. A new store folder that is skipped as `undated or unlabelled` or `no price column` needs a folder rule or a header alias in `scripts/build_database.py` (with a test in `tests/test_build_database.py`); see the schema/data layout checklist in [DEVELOPMENT.md](DEVELOPMENT.md).

### 4.6 Commit in batches

Pushes must stay well under GitHub's 2 GB limit, so commit and push about 500 MB at a time, for example one TÜİK folder per commit:

```bash
du -sh data/raw/*/ | sort -h                 # pick folders that add up to ~500 MB
git add data/raw/01_Food
git commit -m "data: import 01_Food from InflationResearchStudy <commit>"
git push
```

Record the upstream commit from 4.2 in each message. Never commit `*.db` files, `.env`, cookies or browser profiles. Full checklist: [Data update](DEVELOPMENT.md#data-update).

## 5. Run the app

Two terminals:

```bash
uv run python scripts/run_falcon_server.py --engine granian --port 8000
```

```bash
cd frontend && npm run dev
```

| URL | What |
|---|---|
| `http://localhost:5173/` | ucuzu shop: search, product comparison, deals, price alarms |
| `http://localhost:5173/analiz` | inflation analysis dashboard |
| `http://localhost:8000/api/health` | API health; `"database": "available"` means the build worked |

Add `--host 0.0.0.0` to the API command to reach it from other machines. To serve without the dev server (`npm run build` plus a reverse proxy for `/api`), see [How the dashboard reaches the API](GETTING-STARTED.md#how-the-dashboard-reaches-the-api).

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `error: invalid path '…\…'` during checkout | Use `git -c core.protectNTFS=false checkout` (4.2). |
| Sparse checkout is empty in Git Bash | You used a leading `/` in the sparse path; use `git sparse-checkout set --cone InflationItems/Datas Inflations/Datas`. |
| Build fails to replace `data/prices.db` on Windows | Stop the API (and anything else holding the file open), then rebuild. |
| Shop shows 503 `database_outdated` | The database predates the shop columns; rebuild it (section 3). |
| Shop and dashboard show 503 `database_unavailable` | `data/prices.db` (or `PRICES_DB_PATH`) is missing or empty; build it. |
| A new store is missing after an import | Check the build's skip counts; usually the file names have no date or the price header is unknown (4.5). |
| `data_files.py check` fails | Run `data_files.py split`, or add the file to `.gitignore` (4.4). |
