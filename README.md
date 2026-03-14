# strava-oracle

GPS running data explored with six Oracle 26ai workloads - spatial heatmaps, time-series gap-fill, vector similarity, graph queries, JSON-relational duality views, and domain-based integrity constraints.

Full write-up: [From Heart Rate to H3: Running Data in Oracle](https://buckenhofer.com/2026/03/from-heart-rate-to-h3-running-data-oracle)

## The idea

A single set of several GPS runs is loaded into Oracle once and then queried six different ways - no separate engines, no ETL. Each SQL file demonstrates one paradigm of Oracle's converged / multi-model architecture.

| SQL file | Paradigm | What it answers |
|---|---|---|
| `sql/00_setup.sql` | External Tables | Load all CSV files as one Oracle table |
| `sql/01_spatial.sql` | H3 spatial heatmap | Where do I run most often? |
| `sql/02_timeseries.sql` | Gap-fill + smoothing | Reconstruct missing GPS seconds |
| `sql/03_vector.sql` | Vector similarity kNN | Which run felt most like a half-marathon? |
| `sql/04_graph.sql` | SQL/PGQ property graph | Which junctions connect my running network? |
| `sql/05_json.sql` | JSON-relational duality | Serve a run as an API-ready JSON document |
| `sql/06_relational.sql` | Domains + constraints | Reject physically impossible sensor readings |

The data includes half-marathons, interval sessions, and easy morning runs recorded with a GPS watch. Each CSV row contains a timestamp, latitude, longitude, altitude, heart rate, speed, cadence, power, temperature, and distance.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python >= 3.13
- Oracle 26ai - the `latest-full` Docker image is required for H3 spatial support
- Oracle Docker container running on `localhost:1521`, database `FREEPDB1`, dedicated user, e.g. abu

## Setup

**1. Clone and install Python dependencies**

```bash
git clone https://github.com/abuckenhofer/strava-oracle.git
cd strava-oracle
uv sync
```

**2. Convert .fit files to CSV (optional - CSVs already included)**

Raw Garmin `.fit` files live in `data/fit/`. The converter reads each file and writes a date-prefixed CSV to `data/`:

```bash
uv run src/fit_to_csv.py
```

**3. Start Oracle and load the schema**

Copy the CSV files into the container and run the setup script:

```bash
docker cp data/. oracle01:/opt/oracle/data/
docker exec -u oracle oracle01 bash -c \
  "sqlplus -s abu/password@//localhost:1521/FREEPDB1 @/opt/oracle/data/00_setup.sql"
```

Then run the remaining SQL files in order:

```bash
for f in sql/01_spatial.sql sql/02_timeseries.sql sql/03_vector.sql \
          sql/04_graph.sql sql/05_json.sql sql/06_relational.sql; do
  docker exec -u oracle oracle01 bash -c \
    "sqlplus -s abu/password@//localhost:1521/FREEPDB1 @/opt/oracle/data/$(basename $f)"
done
```

or from PowerShell
```PowerShell
$sqlFiles = "sql/01_spatial.sql", "sql/02_timeseries.sql", "sql/03_vector.sql", `
             "sql/04_graph.sql", "sql/05_json.sql", "sql/06_relational.sql"

foreach ($f in $sqlFiles) {
    # Extract just the filename (e.g., 01_spatial.sql)
    $basename = Split-Path $f -Leaf
    
    # Execute inside the Docker container
    docker exec -u oracle oracle01 bash -c "sqlplus -s abu/YourPassword123@//localhost:1521/FREEPDB1 @/opt/oracle/data/$basename"
}
```

## Running the examples

**Generate all figures**

Reads the CSV files directly - no Oracle connection needed:

```bash
uv run src/visualize.py
```

Outputs to `figures/`: GPS route map, H3 heatmap, effort cosine matrix, movement network, HR zone chart.

**Run SQL demos against Oracle**

Executes each SQL paradigm and prints the results:

```bash
uv run src/run_demos.py
```

Requires a running Oracle container and credentials in a `.env` file as in .env.example:

```
ORACLE_DSN=localhost:1521/FREEPDB1
ORACLE_USER=abu
ORACLE_PASSWORD=password
```

## Project structure

```
strava-oracle/
- sql/          SQL scripts (00-06, one per paradigm)
- src/          Python helper scripts
- data/         CSV files (one per run, date-prefixed)
- data/fit/     Raw Garmin .fit files
- figures/      Generated figures for the article
- article.md    Draft of the blog post
- pyproject.toml
- uv.lock
```
