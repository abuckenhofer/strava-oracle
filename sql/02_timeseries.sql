/*  06_timeseries.sql  –  Time Series Analytics
    Gap filling, smoothing, bucketing, and interval detection
    on per-second GPS/HR telemetry.
*/

-- ============================================================
-- 1. Gap Filling  –  time spine + forward-fill
--    GPS can drop for seconds in tunnels or under trees.
--    Build a continuous 1-second spine and fill gaps.
-- ============================================================

-- 1a. Show gaps: seconds where we have no sample
--     Filter to samples with HR > 0 to skip sensor warmup.
WITH run_bounds AS (
    SELECT run_id, MIN(ts) AS t0, MAX(ts) AS t1
      FROM samples
     WHERE heart_rate > 0
     GROUP BY run_id
),
spine AS (
    SELECT rb.run_id,
           rb.t0 + NUMTODSINTERVAL(LEVEL - 1, 'SECOND') AS tick
      FROM run_bounds rb
   CONNECT BY LEVEL <= EXTRACT(DAY FROM (rb.t1 - rb.t0)) * 86400
                      + EXTRACT(HOUR FROM (rb.t1 - rb.t0)) * 3600
                      + EXTRACT(MINUTE FROM (rb.t1 - rb.t0)) * 60
                      + EXTRACT(SECOND FROM (rb.t1 - rb.t0)) + 1
          AND PRIOR rb.run_id = rb.run_id
          AND PRIOR SYS_GUID() IS NOT NULL
)
SELECT sp.run_id,
       sp.tick,
       s.heart_rate,
       s.speed,
       CASE WHEN s.sample_id IS NULL THEN 'GAP' ELSE 'OK' END AS status
  FROM spine sp
  LEFT JOIN samples s ON s.run_id = sp.run_id AND s.ts = sp.tick
 WHERE sp.run_id = 1
 ORDER BY sp.tick
 FETCH FIRST 30 ROWS ONLY;

-- 1b. Forward-fill: carry last known value across gaps
WITH run_bounds AS (
    SELECT run_id, MIN(ts) AS t0, MAX(ts) AS t1
      FROM samples
     WHERE heart_rate > 0
     GROUP BY run_id
),
spine AS (
    SELECT rb.run_id,
           rb.t0 + NUMTODSINTERVAL(LEVEL - 1, 'SECOND') AS tick
      FROM run_bounds rb
     WHERE rb.run_id = 1
   CONNECT BY LEVEL <= EXTRACT(DAY FROM (rb.t1 - rb.t0)) * 86400
                      + EXTRACT(HOUR FROM (rb.t1 - rb.t0)) * 3600
                      + EXTRACT(MINUTE FROM (rb.t1 - rb.t0)) * 60
                      + EXTRACT(SECOND FROM (rb.t1 - rb.t0)) + 1
          AND PRIOR rb.run_id = rb.run_id
          AND PRIOR SYS_GUID() IS NOT NULL
),
joined AS (
    SELECT sp.run_id,
           sp.tick,
           s.heart_rate  AS raw_hr,
           s.speed       AS raw_speed,
           s.lat, s.lon
      FROM spine sp
      LEFT JOIN samples s ON s.run_id = sp.run_id AND s.ts = sp.tick
)
SELECT run_id,
       tick,
       raw_hr,
       LAST_VALUE(raw_hr    IGNORE NULLS) OVER (ORDER BY tick) AS filled_hr,
       raw_speed,
       LAST_VALUE(raw_speed IGNORE NULLS) OVER (ORDER BY tick) AS filled_speed
  FROM joined
 ORDER BY tick
 FETCH FIRST 30 ROWS ONLY;

-- ============================================================
-- 2. Smoothing  –  moving averages (5 s and 30 s windows)
-- ============================================================
SELECT run_id,
       ts,
       heart_rate,
       ROUND(AVG(heart_rate) OVER (
           PARTITION BY run_id ORDER BY ts
           ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING), 1)  AS hr_5s_avg,
       ROUND(AVG(heart_rate) OVER (
           PARTITION BY run_id ORDER BY ts
           ROWS BETWEEN 14 PRECEDING AND 15 FOLLOWING), 1) AS hr_30s_avg,
       speed,
       ROUND(AVG(speed) OVER (
           PARTITION BY run_id ORDER BY ts
           ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING), 3)  AS spd_5s_avg,
       ROUND(AVG(speed) OVER (
           PARTITION BY run_id ORDER BY ts
           ROWS BETWEEN 14 PRECEDING AND 15 FOLLOWING), 3) AS spd_30s_avg
  FROM samples
 WHERE run_id = 1
   AND heart_rate > 0
 ORDER BY ts
 FETCH FIRST 50 ROWS ONLY;

-- ============================================================
-- 3. Bucketing  –  30-second windows with dominant HR zone
-- ============================================================
WITH bucketed AS (
    SELECT run_id,
           TRUNC(ts, 'MI')
              + NUMTODSINTERVAL(
                    FLOOR(EXTRACT(SECOND FROM ts) / 30) * 30,
                    'SECOND')                        AS bucket_start,
           heart_rate,
           speed,
           CASE
               WHEN heart_rate < 110 THEN 'Z1'
               WHEN heart_rate < 130 THEN 'Z2'
               WHEN heart_rate < 150 THEN 'Z3'
               WHEN heart_rate < 170 THEN 'Z4'
               ELSE 'Z5'
           END AS hr_zone
      FROM samples
     WHERE heart_rate > 0
       AND run_id = 1
)
SELECT bucket_start,
       COUNT(*)                     AS samples,
       ROUND(AVG(heart_rate), 1)    AS avg_hr,
       ROUND(AVG(speed), 3)        AS avg_speed,
       STATS_MODE(hr_zone)         AS dominant_zone
  FROM bucketed
 GROUP BY run_id, bucket_start
 ORDER BY bucket_start
 FETCH FIRST 30 ROWS ONLY;

-- ============================================================
-- 4. Interval Detection  –  auto-detect HARD / EASY segments
--    Applied to Intervall_3x2km to find the 3 × 2 km pattern.
-- ============================================================
WITH interval_run AS (
    SELECT s.*, r.filename
      FROM samples s
      JOIN runs r ON r.run_id = s.run_id
     WHERE r.filename = 'Intervall_3x2km.csv'
       AND s.speed > 0
),
classified AS (
    SELECT sample_id, ts, speed, heart_rate, distance,
           CASE WHEN speed >= 10.8 THEN 'HARD' ELSE 'EASY' END AS effort
      FROM interval_run
),
state_change AS (
    SELECT c.*,
           LAG(effort) OVER (ORDER BY ts) AS prev_effort,
           CASE WHEN effort != LAG(effort) OVER (ORDER BY ts)
                  OR LAG(effort) OVER (ORDER BY ts) IS NULL
                THEN 1 ELSE 0
           END AS new_segment
      FROM classified c
),
segments AS (
    SELECT sc.*,
           SUM(new_segment) OVER (ORDER BY ts) AS segment_id
      FROM state_change sc
)
SELECT segment_id,
       effort,
       COUNT(*)                              AS duration_sec,
       ROUND(AVG(speed), 3)                 AS avg_speed,
       ROUND(AVG(heart_rate), 1)            AS avg_hr,
       MIN(ts)                               AS seg_start,
       MAX(ts)                               AS seg_end,
       ROUND(MAX(distance) - MIN(distance)) AS distance_m
  FROM segments
 GROUP BY segment_id, effort
HAVING COUNT(*) >= 30            -- filter micro-segments (< 30 s)
 ORDER BY segment_id;

-- ============================================================
-- 5. HR Drift: first-half vs second-half comparison
--    At constant pace, rising HR signals aerobic decoupling.
--    Applied to HM_Ulm_2025 (hero run).
-- ============================================================
WITH halves AS (
    SELECT s.*,
           NTILE(2) OVER (ORDER BY s.ts) AS half
      FROM samples s
      JOIN runs r ON r.run_id = s.run_id
     WHERE r.filename = 'HM_Ulm_2025.csv'
       AND s.speed > 8
       AND s.heart_rate > 0
)
SELECT half,
       ROUND(AVG(heart_rate), 1)  AS avg_hr,
       ROUND(AVG(speed), 2)       AS avg_speed,
       ROUND(AVG(heart_rate) / NULLIF(AVG(speed), 0), 2) AS hr_per_kmh
  FROM halves
 GROUP BY half
 ORDER BY half;
