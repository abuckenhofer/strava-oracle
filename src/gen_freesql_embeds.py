"""Generate FreeSQL iframe embed codes for each article section.

Each snippet is self-contained: data lives in a CTE, no CREATE TABLE needed.
Output is one iframe HTML block per section, ready to paste into article.md.
"""
import gzip
import base64
import urllib.parse

HEIGHT = "520px"

def make_iframe(section_id, title, sql):
    compressed = gzip.compress(sql.strip().encode("utf-8"), mtime=0)
    # URL-safe base64, no padding — standard for embedding in URLs
    b64 = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    url = (
        "https://freesql.com/embedded/"
        f"?layout=vertical"
        f"&compressed_code={b64}"
        f"&code_language=SQL"
        f"&code_format=false"
    )
    return (
        f'<iframe id="freesql-{section_id}"\n'
        f'  src="{url}"\n'
        f'  height="{HEIGHT}" width="100%" scrolling="no" frameborder="0"\n'
        f'  allowfullscreen="true"\n'
        f'  name="FreeSQL Embedded Playground" title="FreeSQL – {title}"\n'
        f'  style="width:100%;border:1px solid #e0e0e0;'
        f'border-radius:12px;overflow:hidden;">\n'
        f'  FreeSQL Embedded Playground\n'
        f'</iframe>'
    )


# ── 1. Spatial ────────────────────────────────────────────────────────────────
SQL_SPATIAL = """\
-- H3 Heatmap: which ~25 m hex cells do I visit most?
-- GPS sample points from 7 training runs around Ulm, Germany.
-- SDO_UTIL.H3_KEY maps (lat, lon) → H3 cell key at resolution 11.
-- Try changing the resolution (11) to 9 or 10 to see coarser groupings.
WITH gps (run_name, lat, lon) AS (
  SELECT 'HM_Ulm_2025',    48.39810, 9.99240 FROM DUAL UNION ALL
  SELECT 'HM_Ulm_2025',    48.39850, 9.99270 FROM DUAL UNION ALL
  SELECT 'HM_Ulm_2025',    48.39900, 9.99310 FROM DUAL UNION ALL
  SELECT 'HM_Ulm_2025',    48.39810, 9.99240 FROM DUAL UNION ALL  -- revisit
  SELECT 'HM_Ulm_2024',    48.39810, 9.99240 FROM DUAL UNION ALL  -- same cell
  SELECT 'HM_Ulm_2024',    48.39855, 9.99275 FROM DUAL UNION ALL
  SELECT 'Morning_17km',   48.40100, 9.99500 FROM DUAL UNION ALL
  SELECT 'Morning_17km',   48.40150, 9.99550 FROM DUAL UNION ALL
  SELECT 'Morning_17km',   48.39810, 9.99240 FROM DUAL UNION ALL  -- shared cell
  SELECT 'Wednesday_7km',  48.40200, 9.99600 FROM DUAL UNION ALL
  SELECT 'Wednesday_7km',  48.40250, 9.99650 FROM DUAL UNION ALL
  SELECT 'Monday_4km',     48.40300, 9.99700 FROM DUAL
)
SELECT RAWTOHEX(SDO_UTIL.H3_KEY(lat, lon, 11)) AS h3_cell,
       COUNT(*)                                  AS visit_count,
       COUNT(DISTINCT run_name)                  AS runs_through
  FROM gps
 GROUP BY SDO_UTIL.H3_KEY(lat, lon, 11)
 ORDER BY visit_count DESC;
"""

# ── 2. Time Series ────────────────────────────────────────────────────────────
SQL_TIMESERIES = """\
-- Auto interval detection from raw speed telemetry.
-- Data from Intervall_3x2km run — no lap button, just one reading per minute.
-- A SUM() over state changes groups consecutive seconds into named segments.
-- Try changing the threshold (10.8) to see how the detected blocks shift.
WITH raw_speed (ts, speed_kmh) AS (
  SELECT TIMESTAMP '2025-09-03 06:00:00',  8.2 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:01:00',  8.5 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:02:00',  8.1 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:03:00', 12.4 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:04:00', 13.1 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:05:00', 12.9 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:06:00', 13.3 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:07:00', 12.8 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:08:00', 13.0 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:09:00', 13.2 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:10:00',  7.9 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:11:00',  8.0 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:12:00',  7.8 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:13:00', 13.0 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:14:00', 13.2 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:15:00', 13.1 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:16:00', 13.4 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:17:00', 13.0 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:18:00', 12.9 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:19:00',  8.2 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:20:00',  8.0 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:21:00',  7.9 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:22:00', 12.8 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:23:00', 13.1 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:24:00', 13.3 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:25:00', 13.0 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:26:00', 13.2 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:27:00',  8.1 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:28:00',  8.3 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-03 06:29:00',  8.0 FROM DUAL
),
classified AS (
  SELECT ts, speed_kmh,
         CASE WHEN speed_kmh >= 10.8 THEN 'HARD' ELSE 'EASY' END AS effort,
         LAG(CASE WHEN speed_kmh >= 10.8 THEN 'HARD' ELSE 'EASY' END)
             OVER (ORDER BY ts) AS prev_effort
    FROM raw_speed
),
segmented AS (
  SELECT ts, speed_kmh, effort,
         SUM(CASE WHEN effort != prev_effort OR prev_effort IS NULL THEN 1 ELSE 0 END)
             OVER (ORDER BY ts) AS segment_id
    FROM classified
)
SELECT segment_id,
       effort,
       MIN(ts)                  AS starts_at,
       COUNT(*)                 AS duration_min,
       ROUND(AVG(speed_kmh), 1) AS avg_speed_kmh
  FROM segmented
 GROUP BY segment_id, effort
 ORDER BY segment_id;
"""

# ── 3. Vector ─────────────────────────────────────────────────────────────────
SQL_VECTOR = """\
-- Effort signature kNN: which run felt most like my half-marathon?
-- Each run is an 11-dim vector:
--   dims 1-5 : % time in HR zones 1-5
--   dim  6   : normalised avg speed
--   dim  7   : normalised avg HR
--   dim  8   : speed coefficient of variation
--   dims 9-11: % time in pace zones (slow / moderate / fast)
-- VECTOR_DISTANCE(COSINE) ranks runs by physiological similarity.
-- Try changing the reference run in the WHERE clause.
WITH run_vectors (filename, features) AS (
  SELECT 'HM_Ulm_2025.csv',
    TO_VECTOR('[0.05,0.15,0.40,0.35,0.05,0.72,0.78,0.12,0.10,0.65,0.25]', 11, FLOAT32) FROM DUAL UNION ALL
  SELECT 'HM_Ulm_2024.csv',
    TO_VECTOR('[0.08,0.20,0.35,0.30,0.07,0.68,0.75,0.15,0.15,0.60,0.25]', 11, FLOAT32) FROM DUAL UNION ALL
  SELECT 'Intervall_3x2km.csv',
    TO_VECTOR('[0.25,0.20,0.30,0.20,0.05,0.70,0.76,0.30,0.30,0.45,0.25]', 11, FLOAT32) FROM DUAL UNION ALL
  SELECT 'Morning_run_17km.csv',
    TO_VECTOR('[0.10,0.30,0.40,0.18,0.02,0.62,0.72,0.10,0.20,0.65,0.15]', 11, FLOAT32) FROM DUAL UNION ALL
  SELECT 'Intervall_4x1km.csv',
    TO_VECTOR('[0.30,0.20,0.25,0.20,0.05,0.68,0.74,0.35,0.35,0.40,0.25]', 11, FLOAT32) FROM DUAL UNION ALL
  SELECT 'Wednesday_7km.csv',
    TO_VECTOR('[0.20,0.40,0.30,0.10,0.00,0.60,0.68,0.08,0.30,0.60,0.10]', 11, FLOAT32) FROM DUAL UNION ALL
  SELECT 'Monday_4km.csv',
    TO_VECTOR('[0.30,0.45,0.20,0.05,0.00,0.55,0.65,0.07,0.40,0.55,0.05]', 11, FLOAT32) FROM DUAL
)
SELECT v.filename,
       ROUND(VECTOR_DISTANCE(v.features, ref.features, COSINE), 4) AS cosine_distance
  FROM run_vectors v
 CROSS JOIN (SELECT features FROM run_vectors
              WHERE filename = 'HM_Ulm_2025.csv') ref
 WHERE v.filename != 'HM_Ulm_2025.csv'
 ORDER BY cosine_distance;
"""

# ── 4. Graph ──────────────────────────────────────────────────────────────────
SQL_GRAPH = """\
-- Movement network: derive H3 cell transitions and find hub locations.
-- Location names stand in for real H3 hex IDs — the computation is identical.
-- LEAD() pairs each cell with the next one in time order per run.
-- The final GROUP BY counts how many distinct directions I leave each cell.
-- Try adding a new run or rerouting an existing one to shift hub rankings.
WITH gps_seq (run_id, run_name, seq, cell) AS (
  SELECT 1, 'HM_Ulm_2025',  1, 'Bridge_N'   FROM DUAL UNION ALL
  SELECT 1, 'HM_Ulm_2025',  2, 'Bridge_S'   FROM DUAL UNION ALL
  SELECT 1, 'HM_Ulm_2025',  3, 'River_E'    FROM DUAL UNION ALL
  SELECT 1, 'HM_Ulm_2025',  4, 'Markt_NW'   FROM DUAL UNION ALL
  SELECT 1, 'HM_Ulm_2025',  5, 'Markt_S'    FROM DUAL UNION ALL
  SELECT 2, 'HM_Ulm_2024',  1, 'Bridge_N'   FROM DUAL UNION ALL
  SELECT 2, 'HM_Ulm_2024',  2, 'Bridge_S'   FROM DUAL UNION ALL
  SELECT 2, 'HM_Ulm_2024',  3, 'River_E'    FROM DUAL UNION ALL
  SELECT 2, 'HM_Ulm_2024',  4, 'Donau_Ufer' FROM DUAL UNION ALL
  SELECT 3, 'Morning_17km', 1, 'Bridge_N'   FROM DUAL UNION ALL
  SELECT 3, 'Morning_17km', 2, 'Bridge_S'   FROM DUAL UNION ALL
  SELECT 3, 'Morning_17km', 3, 'Stadtmitte' FROM DUAL UNION ALL
  SELECT 3, 'Morning_17km', 4, 'Markt_NW'   FROM DUAL UNION ALL
  SELECT 3, 'Morning_17km', 5, 'Markt_S'    FROM DUAL UNION ALL
  SELECT 4, 'Intervall_3x', 1, 'Donauhalle' FROM DUAL UNION ALL
  SELECT 4, 'Intervall_3x', 2, 'Stadion'    FROM DUAL UNION ALL
  SELECT 4, 'Intervall_3x', 3, 'Donauhalle' FROM DUAL UNION ALL
  SELECT 4, 'Intervall_3x', 4, 'Stadion'    FROM DUAL
),
transitions AS (
  SELECT cell AS source_cell,
         LEAD(cell) OVER (PARTITION BY run_id ORDER BY seq) AS target_cell
    FROM gps_seq
),
movement_edges AS (
  SELECT source_cell, target_cell, COUNT(*) AS transition_count
    FROM transitions
   WHERE target_cell IS NOT NULL
     AND source_cell != target_cell
   GROUP BY source_cell, target_cell
)
SELECT source_cell,
       COUNT(DISTINCT target_cell)  AS out_degree,
       SUM(transition_count)        AS total_exits,
       LISTAGG(target_cell, ' → ')
           WITHIN GROUP (ORDER BY transition_count DESC) AS exits_to
  FROM movement_edges
 GROUP BY source_cell
 ORDER BY out_degree DESC, total_exits DESC;
"""

# ── 5. JSON ───────────────────────────────────────────────────────────────────
SQL_JSON = """\
-- Assemble a complete run document from normalised relational rows.
-- This is the transformation JSON Relational Duality Views automate:
-- the app thinks in documents, the database stores rows — no ORM needed.
-- Try adding more samples or a new field to the JSON_OBJECT.
WITH run_data (run_id, filename, distance_km, sport) AS (
  SELECT 5, 'HM_Ulm_2025.csv', 21.3, 'running' FROM DUAL
),
sample_data (sample_id, run_id, ts, lat, lon, speed, heart_rate) AS (
  SELECT 40001, 5, TIMESTAMP '2025-09-28 07:23:28', 48.39810, 9.99240, 0.0,  87 FROM DUAL UNION ALL
  SELECT 40002, 5, TIMESTAMP '2025-09-28 07:23:29', 48.39815, 9.99250, 0.5,  88 FROM DUAL UNION ALL
  SELECT 40003, 5, TIMESTAMP '2025-09-28 07:23:30', 48.39820, 9.99260, 1.2,  89 FROM DUAL UNION ALL
  SELECT 40004, 5, TIMESTAMP '2025-09-28 07:23:31', 48.39825, 9.99270, 2.8,  91 FROM DUAL UNION ALL
  SELECT 40005, 5, TIMESTAMP '2025-09-28 07:23:32', 48.39830, 9.99280, 4.1,  93 FROM DUAL
)
SELECT JSON_OBJECT(
    '_id'      VALUE r.run_id,
    'filename' VALUE r.filename,
    'sport'    VALUE r.sport,
    'distance' VALUE r.distance_km,
    'samples'  VALUE JSON_ARRAYAGG(
                   JSON_OBJECT(
                       'sampleId'  VALUE s.sample_id,
                       'ts'        VALUE TO_CHAR(s.ts, 'YYYY-MM-DD"T"HH24:MI:SS".000Z"'),
                       'lat'       VALUE s.lat,
                       'lon'       VALUE s.lon,
                       'speed'     VALUE s.speed,
                       'heartRate' VALUE s.heart_rate
                   ) ORDER BY s.sample_id
               )
    RETURNING CLOB
) AS run_document
  FROM run_data r
  JOIN sample_data s ON s.run_id = r.run_id
 GROUP BY r.run_id, r.filename, r.sport, r.distance_km;
"""

# ── 6. Relational ─────────────────────────────────────────────────────────────
SQL_RELATIONAL = """\
-- Validate GPS telemetry against physical domain constraints.
-- Three rows contain deliberate bad values — can you spot them before running?
-- This is the logic Oracle SQL Domains enforce automatically at write time.
-- Try adding your own invalid row to see it caught.
WITH telemetry (ts, heart_rate, latitude, longitude, speed_kmh, altitude_km) AS (
  SELECT TIMESTAMP '2025-09-28 07:23:28',  87, 48.39810,   9.99240,  0.0, 0.476 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-28 07:24:00', 142, 48.39900,   9.99300, 12.3, 0.478 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-28 07:24:30', 999, 48.39950,   9.99350, 11.8, 0.480 FROM DUAL UNION ALL  -- bad HR
  SELECT TIMESTAMP '2025-09-28 07:25:00', 155, 200.00000,  9.99400, 12.1, 0.482 FROM DUAL UNION ALL  -- bad lat
  SELECT TIMESTAMP '2025-09-28 07:25:30', 158, 48.40000,   9.99450, -5.0, 0.484 FROM DUAL UNION ALL  -- bad speed
  SELECT TIMESTAMP '2025-09-28 07:26:00', 161, 48.40050,   9.99500, 12.8, 0.486 FROM DUAL UNION ALL
  SELECT TIMESTAMP '2025-09-28 07:26:30', 163, 48.40100,   9.99550, 13.0, 0.488 FROM DUAL
)
SELECT ts,
       heart_rate AS hr,
       latitude   AS lat,
       speed_kmh,
       CASE
           WHEN heart_rate  NOT BETWEEN 0    AND 300 THEN 'INVALID heart_rate ('  || heart_rate  || ')'
           WHEN latitude    NOT BETWEEN -90  AND 90  THEN 'INVALID latitude ('    || latitude    || ')'
           WHEN longitude   NOT BETWEEN -180 AND 180 THEN 'INVALID longitude ('   || longitude   || ')'
           WHEN speed_kmh   < 0                      THEN 'INVALID speed ('       || speed_kmh   || ')'
           WHEN altitude_km NOT BETWEEN -0.5 AND 9   THEN 'INVALID altitude ('    || altitude_km || ')'
           ELSE 'VALID'
       END AS validation_result
  FROM telemetry
 ORDER BY ts;
"""


sections = [
    ("spatial",    "H3 Heatmap",              SQL_SPATIAL),
    ("timeseries", "Interval Detection",       SQL_TIMESERIES),
    ("vector",     "Effort Signature kNN",     SQL_VECTOR),
    ("graph",      "Movement Network",         SQL_GRAPH),
    ("json",       "JSON Document Assembly",   SQL_JSON),
    ("relational", "Telemetry Validation",     SQL_RELATIONAL),
]

for section_id, title, sql in sections:
    print(f"\n{'='*72}")
    print(f"SECTION: {title}  [{section_id}]")
    print('='*72)
    print(make_iframe(section_id, title, sql))
