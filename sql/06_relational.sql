/*  02_relational.sql  –  Four relational sub-demos
    1. One Source, Three Views   (relational / JSON / graph)
    2. SQL Domains               (23ai self-documenting constraints)
    3. GROUP BY alias            (23ai readability improvement)
    4. Integrity Constraints     (why DB beats app code)
*/

-- ============================================================
-- 1. One Source, Three Views
--    The same sample row seen as a relational row, a JSON
--    document, and a graph vertex – zero data movement.
-- ============================================================

-- 1a. Relational view
SELECT sample_id, run_id, ts, lat, lon, heart_rate, speed
  FROM samples
 WHERE run_id = 1
   AND heart_rate > 0
   AND speed > 0
   AND ROWNUM <= 3;

-- 1b. JSON view (JSON_OBJECT)
SELECT JSON_OBJECT(
           'sampleId'  : sample_id,
           'ts'        : ts,
           'location'  : JSON_OBJECT('lat' : lat, 'lon' : lon),
           'heartRate' : heart_rate,
           'speed'     : speed
       RETURNING CLOB PRETTY) AS sample_json
  FROM samples
 WHERE run_id = 1
   AND heart_rate > 0
   AND speed > 0
   AND ROWNUM <= 3;

-- 1c. Graph vertex reference (SQL/PGQ – query only, graph created in 04)
-- This demonstrates the same physical row being addressable
-- via MATCH once the property graph exists.
-- (Preview – full graph demo in 04_graph.sql)

-- ============================================================
-- 2. SQL Domains  (23ai / 26ai)
--    Declare intent at the column level.
-- ============================================================

-- 2a. Create domains
CREATE DOMAIN IF NOT EXISTS bpm_domain AS NUMBER(5,1)
    CONSTRAINT bpm_range CHECK (bpm_domain BETWEEN 0 AND 300)
    DISPLAY 'BPM';

CREATE DOMAIN IF NOT EXISTS latitude_domain AS NUMBER(10,7)
    CONSTRAINT lat_range CHECK (latitude_domain BETWEEN -90 AND 90)
    DISPLAY 'degrees latitude';

CREATE DOMAIN IF NOT EXISTS longitude_domain AS NUMBER(10,7)
    CONSTRAINT lon_range CHECK (longitude_domain BETWEEN -180 AND 180)
    DISPLAY 'degrees longitude';

CREATE DOMAIN IF NOT EXISTS speed_kmh_domain AS NUMBER(8,4)
    CONSTRAINT speed_kmh_range CHECK (speed_kmh_domain >= 0)
    DISPLAY 'km/h';

CREATE DOMAIN IF NOT EXISTS altitude_domain AS NUMBER(6,3)
    CONSTRAINT alt_range CHECK (altitude_domain BETWEEN -0.5 AND 9.0)
    DISPLAY 'km';

-- 2c. Apply domains to a typed view
CREATE OR REPLACE VIEW samples_typed AS
SELECT sample_id,
       run_id,
       ts,
       CAST(lat        AS latitude_domain)   AS lat,
       CAST(lon        AS longitude_domain)   AS lon,
       CAST(heart_rate AS bpm_domain)         AS heart_rate,
       CAST(speed      AS speed_kmh_domain)   AS speed,
       CAST(altitude   AS altitude_domain)    AS altitude
  FROM samples;

-- 2d. Demo: domain constraint violation
-- This INSERT will fail because 999 exceeds bpm_domain (0-300).
-- Uncomment to test:
-- INSERT INTO samples (run_id, ts, heart_rate)
--     VALUES (1, TIMESTAMP '2099-01-01 00:00:00', 999);

-- Show domain metadata
SELECT column_name, domain_owner, domain_name
  FROM user_tab_columns
 WHERE table_name = 'SAMPLES_TYPED'
   AND domain_name IS NOT NULL
 ORDER BY column_id;

-- ============================================================
-- 3. GROUP BY alias  (23ai feature)
--    Use the CASE alias directly in GROUP BY – no subquery needed.
-- ============================================================

-- 3a. Heart-rate zones
SELECT CASE
           WHEN heart_rate < 110 THEN 'Z1 Easy'
           WHEN heart_rate < 130 THEN 'Z2 Aerobic'
           WHEN heart_rate < 150 THEN 'Z3 Tempo'
           WHEN heart_rate < 170 THEN 'Z4 Threshold'
           ELSE                       'Z5 Max'
       END                             AS hr_zone,
       COUNT(*)                        AS samples,
       ROUND(AVG(speed), 2)           AS avg_speed_kmh,
       ROUND(MIN(heart_rate))         AS min_hr,
       ROUND(MAX(heart_rate))         AS max_hr
  FROM samples
 WHERE heart_rate > 0
 GROUP BY hr_zone                      -- 23ai: alias in GROUP BY
 ORDER BY hr_zone;

-- 3b. Pace zones
SELECT CASE
           WHEN speed < 9.0  THEN 'Slow  (>6:40/km)'
           WHEN speed < 12.0 THEN 'Moderate (5:00-6:40/km)'
           ELSE                    'Fast  (<5:00/km)'
       END                             AS pace_zone,
       COUNT(*)                        AS samples,
       ROUND(AVG(heart_rate))         AS avg_hr,
       ROUND(AVG(speed), 2)           AS avg_speed
  FROM samples
 WHERE speed > 0
 GROUP BY pace_zone                    -- 23ai: alias in GROUP BY
 ORDER BY pace_zone;

-- ============================================================
-- 4. Integrity Constraints
--    Real rules that matter in fitness telemetry.
-- ============================================================

-- 4a. UNIQUE(run_id, ts) already exists → no duplicate timestamps per run
-- Try inserting a duplicate:
-- INSERT INTO samples (run_id, ts, lat, lon)
--     SELECT run_id, ts, lat, lon
--       FROM samples WHERE ROWNUM = 1;
-- → ORA-00001: unique constraint violated

-- 4b. Timestamp bounds: every sample ts within the run window
SELECT r.filename,
       r.start_time                          AS run_start,
       r.start_time + NUMTODSINTERVAL(r.total_elapsed_time, 'SECOND') AS run_end,
       MIN(s.ts)                             AS first_sample,
       MAX(s.ts)                             AS last_sample,
       CASE WHEN MIN(s.ts) >= r.start_time
             AND MAX(s.ts) <= r.start_time
                             + NUMTODSINTERVAL(r.total_elapsed_time + 1, 'SECOND')
            THEN 'VALID' ELSE 'OUT OF BOUNDS'
       END                                   AS bounds_check
  FROM runs r
  JOIN samples s ON s.run_id = r.run_id
 GROUP BY r.run_id, r.filename, r.start_time, r.total_elapsed_time;

-- 4c. FK cascade protection: cannot delete a run that has samples
-- DELETE FROM runs WHERE run_id = 1;
-- → ORA-02292: integrity constraint violated - child record found

-- 4d. Minimum-samples check (analytic validation)
SELECT r.filename,
       COUNT(*)       AS sample_count,
       CASE WHEN COUNT(*) >= 100 THEN 'OK' ELSE 'TOO FEW' END AS quality
  FROM runs r
  JOIN samples s ON s.run_id = r.run_id
 GROUP BY r.run_id, r.filename
 ORDER BY sample_count;
