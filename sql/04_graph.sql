/*  04_graph.sql  –  Movement Network (SQL/PGQ)

    Models GPS movement as a directed graph of H3 cell transitions.
    Nodes  = distinct H3 cells visited (resolution 11, ~25 m).
    Edges  = directed steps between consecutive cells within a run.

    Hub cells: which nodes have the highest out-degree?
               (most distinct exit directions — junctions in the route network)
*/

-- ============================================================
-- 1. movement_transitions  –  consecutive H3 cell pairs
--    LEAD() over time-ordered samples produces one row per step.
-- ============================================================
DROP TABLE movement_transitions PURGE;

CREATE TABLE movement_transitions AS
WITH tagged AS (
    SELECT run_id, ts, speed,
           RAWTOHEX(SDO_UTIL.H3_KEY(lat, lon, 11)) AS h3_cell
      FROM samples
     WHERE lat IS NOT NULL
)
SELECT run_id,
       h3_cell                                              AS source_cell,
       LEAD(h3_cell) OVER (PARTITION BY run_id ORDER BY ts) AS target_cell,
       speed
  FROM tagged;

-- Remove run-end rows (no next cell) and stationary self-loops
DELETE FROM movement_transitions
 WHERE target_cell IS NULL
    OR source_cell = target_cell;
COMMIT;

-- ============================================================
-- 2. movement_nodes  –  one row per distinct H3 cell
-- ============================================================
DROP TABLE movement_nodes PURGE;

CREATE TABLE movement_nodes AS
SELECT RAWTOHEX(SDO_UTIL.H3_KEY(lat, lon, 11)) AS h3_cell,
       COUNT(*)                                  AS visit_count,
       COUNT(DISTINCT run_id)                    AS runs_through
  FROM samples
 WHERE lat IS NOT NULL
 GROUP BY RAWTOHEX(SDO_UTIL.H3_KEY(lat, lon, 11));

ALTER TABLE movement_nodes ADD CONSTRAINT mn_pk PRIMARY KEY (h3_cell);

-- ============================================================
-- 3. movement_edges  –  aggregated cell-to-cell transitions
-- ============================================================
DROP TABLE movement_edges PURGE;

CREATE TABLE movement_edges AS
SELECT source_cell,
       target_cell,
       COUNT(*)              AS transition_count,
       ROUND(AVG(speed), 2) AS avg_speed
  FROM movement_transitions
 GROUP BY source_cell, target_cell;

ALTER TABLE movement_edges ADD CONSTRAINT me_pk PRIMARY KEY (source_cell, target_cell);

-- ============================================================
-- 4. Property Graph definition
-- ============================================================
CREATE OR REPLACE PROPERTY GRAPH movement_network
    VERTEX TABLES (
        movement_nodes KEY (h3_cell)
            PROPERTIES (visit_count, runs_through)
    )
    EDGE TABLES (
        movement_edges AS moves_to
            KEY (source_cell, target_cell)
            SOURCE      KEY (source_cell) REFERENCES movement_nodes (h3_cell)
            DESTINATION KEY (target_cell) REFERENCES movement_nodes (h3_cell)
            PROPERTIES (transition_count, avg_speed)
    );

-- ============================================================
-- 5. Hub cells  –  highest out-degree
--    Which H3 cells do I leave in the most distinct directions?
--    Centrality requires a self-join in plain SQL; MATCH aggregates it directly.
-- ============================================================
SELECT source_cell,
       visit_count,
       COUNT(DISTINCT target_cell) AS out_degree,
       SUM(transition_count)       AS total_exits
  FROM GRAPH_TABLE (movement_network
         MATCH (a) -[e IS moves_to]-> (b)
         COLUMNS (a.h3_cell AS source_cell, a.visit_count,
                  b.h3_cell AS target_cell, e.transition_count))
 GROUP BY source_cell, visit_count
 ORDER BY out_degree DESC, total_exits DESC
 FETCH FIRST 10 ROWS ONLY;
