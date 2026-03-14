/*  03_spatial.sql  –  H3 Heatmap
    Uses SDO_UTIL.H3_KEY (Oracle 23ai / 26ai) to map GPS points
    to H3 hexagonal cells and build a run heatmap.
    Requires: gvenzl/oracle-free:latest-full (spatial support).
*/

-- ============================================================
-- 1. H3 index at resolution 9 (block-level, ~174 m edge)
-- ============================================================
CREATE OR REPLACE VIEW samples_h3 AS
SELECT s.sample_id,
       s.run_id,
       s.ts,
       s.lat,
       s.lon,
       s.heart_rate,
       s.speed,
       RAWTOHEX(SDO_UTIL.H3_KEY(s.lat, s.lon, 9))  AS h3_cell
  FROM samples s
 WHERE s.lat IS NOT NULL
   AND s.lon IS NOT NULL;

-- ============================================================
-- 2. Heatmap aggregation: visits, avg HR, avg speed per cell
-- ============================================================
SELECT h3_cell,
       COUNT(*)                   AS visit_count,
       ROUND(AVG(heart_rate), 1)  AS avg_hr,
       ROUND(AVG(speed), 3)      AS avg_speed_kmh,
       COUNT(DISTINCT run_id)     AS runs_through
  FROM samples_h3
 GROUP BY h3_cell
 ORDER BY visit_count DESC
 FETCH FIRST 20 ROWS ONLY;

-- ============================================================
-- 3. Top 10 hottest cells
-- ============================================================
SELECT h3_cell,
       visit_count,
       avg_hr,
       avg_speed_kmh,
       runs_through
  FROM (
      SELECT h3_cell,
             COUNT(*)                   AS visit_count,
             ROUND(AVG(heart_rate), 1)  AS avg_hr,
             ROUND(AVG(speed), 3)      AS avg_speed_kmh,
             COUNT(DISTINCT run_id)     AS runs_through
        FROM samples_h3
       GROUP BY h3_cell
  )
 ORDER BY visit_count DESC
 FETCH FIRST 10 ROWS ONLY;

-- ============================================================
-- 4. Multi-run overlap: cells visited by 2+ distinct runs
-- ============================================================
SELECT h3_cell,
       COUNT(DISTINCT run_id)     AS num_runs,
       COUNT(*)                   AS total_visits,
       ROUND(AVG(heart_rate), 1)  AS avg_hr,
       ROUND(AVG(speed), 3)      AS avg_speed
  FROM samples_h3
 GROUP BY h3_cell
HAVING COUNT(DISTINCT run_id) >= 2
 ORDER BY total_visits DESC
 FETCH FIRST 20 ROWS ONLY;

-- ============================================================
-- 5. Resolution comparison: resolution 7 (~5.2 km² area)
-- ============================================================
SELECT RAWTOHEX(SDO_UTIL.H3_KEY(lat, lon, 7))  AS h3_coarse,
       COUNT(*)                       AS visit_count,
       COUNT(DISTINCT run_id)         AS runs_through,
       ROUND(AVG(heart_rate), 1)      AS avg_hr
  FROM samples
 WHERE lat IS NOT NULL
 GROUP BY SDO_UTIL.H3_KEY(lat, lon, 7)
 ORDER BY visit_count DESC;
