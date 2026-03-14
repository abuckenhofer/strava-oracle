/*  05_vector.sql  –  Vector Similarity
    Build an 11-dimensional "effort signature" per run, store as
    VECTOR(11, FLOAT32), then use VECTOR_DISTANCE for kNN search.
*/

-- ============================================================
-- 1. run_features_v  –  11 feature dimensions per run
--    Dimensions:
--      1-5: HR zone percentages (z1..z5)
--        6: normalised avg speed
--        7: normalised avg HR
--        8: speed coefficient of variation
--      9-11: pace zone percentages (slow / moderate / fast)
-- ============================================================
CREATE OR REPLACE VIEW run_features_v AS
WITH hr_zones AS (
    SELECT run_id,
           COUNT(*)                                            AS total,
           SUM(CASE WHEN heart_rate > 0   AND heart_rate < 110 THEN 1 ELSE 0 END) AS z1,
           SUM(CASE WHEN heart_rate >= 110 AND heart_rate < 130 THEN 1 ELSE 0 END) AS z2,
           SUM(CASE WHEN heart_rate >= 130 AND heart_rate < 150 THEN 1 ELSE 0 END) AS z3,
           SUM(CASE WHEN heart_rate >= 150 AND heart_rate < 170 THEN 1 ELSE 0 END) AS z4,
           SUM(CASE WHEN heart_rate >= 170                      THEN 1 ELSE 0 END) AS z5
      FROM samples
     WHERE heart_rate > 0
     GROUP BY run_id
),
speed_stats AS (
    SELECT run_id,
           AVG(speed)                                    AS avg_spd,
           STDDEV(speed)                                 AS std_spd,
           COUNT(*)                                      AS total,
           SUM(CASE WHEN speed > 0 AND speed < 9.0  THEN 1 ELSE 0 END) AS slow,
           SUM(CASE WHEN speed >= 9.0 AND speed < 12.0 THEN 1 ELSE 0 END) AS moderate,
           SUM(CASE WHEN speed >= 12.0               THEN 1 ELSE 0 END) AS fast
      FROM samples
     WHERE speed > 0
     GROUP BY run_id
),
global_range AS (
    SELECT MAX(avg_speed) AS max_spd,
           MAX(avg_heart_rate) AS max_hr
      FROM runs
)
SELECT h.run_id,
       -- HR zone percentages
       ROUND(h.z1 / h.total, 4) AS pct_z1,
       ROUND(h.z2 / h.total, 4) AS pct_z2,
       ROUND(h.z3 / h.total, 4) AS pct_z3,
       ROUND(h.z4 / h.total, 4) AS pct_z4,
       ROUND(h.z5 / h.total, 4) AS pct_z5,
       -- Normalised avg speed  (0..1)
       ROUND(r.avg_speed / g.max_spd, 4) AS norm_speed,
       -- Normalised avg HR     (0..1)
       ROUND(r.avg_heart_rate / g.max_hr, 4) AS norm_hr,
       -- Speed coefficient of variation
       ROUND(CASE WHEN sp.avg_spd > 0 THEN sp.std_spd / sp.avg_spd ELSE 0 END, 4) AS speed_cv,
       -- Pace zone percentages
       ROUND(sp.slow     / sp.total, 4) AS pct_slow,
       ROUND(sp.moderate / sp.total, 4) AS pct_moderate,
       ROUND(sp.fast     / sp.total, 4) AS pct_fast
  FROM hr_zones h
  JOIN speed_stats sp ON sp.run_id = h.run_id
  JOIN runs r         ON r.run_id  = h.run_id
 CROSS JOIN global_range g;

-- Preview the feature vectors
SELECT * FROM run_features_v;

-- ============================================================
-- 2. run_vectors  –  materialise as VECTOR(11, FLOAT32)
-- ============================================================
DROP TABLE run_vectors PURGE;

CREATE TABLE run_vectors (
    run_id     NUMBER CONSTRAINT rv_pk PRIMARY KEY
                      CONSTRAINT rv_fk REFERENCES runs(run_id),
    filename   VARCHAR2(200),
    features   VECTOR(11, FLOAT32)
);

INSERT INTO run_vectors (run_id, filename, features)
SELECT f.run_id,
       r.filename,
       TO_VECTOR(
           '[' || f.pct_z1      || ',' || f.pct_z2      || ','
               || f.pct_z3      || ',' || f.pct_z4      || ','
               || f.pct_z5      || ',' || f.norm_speed   || ','
               || f.norm_hr     || ',' || f.speed_cv     || ','
               || f.pct_slow    || ',' || f.pct_moderate || ','
               || f.pct_fast    || ']',
           11, FLOAT32
       )
  FROM run_features_v f
  JOIN runs r ON r.run_id = f.run_id;

COMMIT;

-- ============================================================
-- 3. kNN  –  "find runs most similar to HM_Ulm"
-- ============================================================
SELECT v.filename,
       ROUND(VECTOR_DISTANCE(v.features, ref.features, COSINE), 4) AS cosine_dist
  FROM run_vectors v
 CROSS JOIN (SELECT features FROM run_vectors
              WHERE filename = 'HM_Ulm_2025.csv') ref
 WHERE v.filename != 'HM_Ulm_2025.csv'
 ORDER BY cosine_dist
 FETCH FIRST 3 ROWS ONLY;

-- ============================================================
-- 4. Cosine vs Euclidean comparison
--    Same reference run, two distance metrics side by side.
-- ============================================================
SELECT v.filename,
       ROUND(VECTOR_DISTANCE(v.features, ref.features, COSINE), 4)    AS cosine_dist,
       ROUND(VECTOR_DISTANCE(v.features, ref.features, EUCLIDEAN), 4) AS euclidean_dist
  FROM run_vectors v
 CROSS JOIN (SELECT features FROM run_vectors
              WHERE filename = 'HM_Ulm_2025.csv') ref
 WHERE v.filename != 'HM_Ulm_2025.csv'
 ORDER BY cosine_dist;

-- ============================================================
-- 5. Full pairwise similarity matrix
-- ============================================================
SELECT a.filename                                          AS run_a,
       b.filename                                          AS run_b,
       ROUND(VECTOR_DISTANCE(a.features, b.features, COSINE), 4) AS cosine_dist
  FROM run_vectors a
  JOIN run_vectors b ON a.run_id < b.run_id
 ORDER BY cosine_dist;

-- ============================================================
-- 6. Explainability: what each dimension means
-- ============================================================
SELECT run_id,
       filename,
       f.pct_z1   AS "Z1 Easy %",
       f.pct_z2   AS "Z2 Aerobic %",
       f.pct_z3   AS "Z3 Tempo %",
       f.pct_z4   AS "Z4 Threshold %",
       f.pct_z5   AS "Z5 Max %",
       f.norm_speed AS "Norm Speed",
       f.norm_hr    AS "Norm HR",
       f.speed_cv   AS "Speed CV",
       f.pct_slow   AS "Pace Slow %",
       f.pct_moderate AS "Pace Mod %",
       f.pct_fast   AS "Pace Fast %"
  FROM run_features_v f
  JOIN runs r USING (run_id)
 ORDER BY run_id;
