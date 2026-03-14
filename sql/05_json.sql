/*  01_json.sql  –  JSON-Relational Duality Views
    Oracle 23ai / 26ai feature: expose normalised tables as JSON documents
    and vice-versa, with full DML support.
*/

-- ============================================================
-- 1. run_dv  –  duality view: each run as a JSON document
-- ============================================================
CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW run_dv AS
    runs @INSERT @UPDATE @DELETE
    {
        _id         : run_id,
        filename    : filename,
        sport       : sport,
        startTime   : start_time,
        distance    : total_distance,
        elapsedTime : total_elapsed_time,
        avgHR       : avg_heart_rate,
        maxHR       : max_heart_rate,
        avgSpeed    : avg_speed,
        startLat    : start_lat,
        startLon    : start_lon
    };

-- ============================================================
-- 2. sample_card_dv  –  read-only "run card" with sample array
-- ============================================================
CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW sample_card_dv AS
    runs @NOCHECK
    {
        _id        : run_id,
        filename   : filename,
        sport      : sport,
        distance   : total_distance,
        samples : samples @NOCHECK
        [
            {
                sampleId   : sample_id,
                ts         : ts,
                lat        : lat,
                lon        : lon,
                altitude   : altitude,
                speed      : speed,
                heartRate  : heart_rate,
                cadence    : cadence,
                power      : power
            }
        ]
    };

-- ============================================================
-- 3. Demo queries
-- ============================================================

-- 3a. Dot-notation: get run details
SELECT r.data.filename,
       r.data.distance,
       r.data.avgHR,
       r.data.avgSpeed
  FROM run_dv r
 WHERE r.data.filename = 'HM_Ulm_2025.csv';

-- 3b. JSON_TABLE on the duality view – flatten run attributes
SELECT j.*
  FROM run_dv r,
       JSON_TABLE(r.data, '$'
           COLUMNS (
               filename     VARCHAR2(100) PATH '$.filename',
               distance     NUMBER        PATH '$.distance',
               elapsed_time NUMBER        PATH '$.elapsedTime',
               avg_hr       NUMBER        PATH '$.avgHR',
               avg_speed    NUMBER        PATH '$.avgSpeed'
           )
       ) j
 ORDER BY j.filename;

-- 3c. Read a sample card (first 5 samples)
SELECT j.*
  FROM sample_card_dv r,
       JSON_TABLE(r.data, '$'
           COLUMNS (
               filename    VARCHAR2(100) PATH '$.filename',
               NESTED PATH '$.samples[0 to 4]'
               COLUMNS (
                   ts       VARCHAR2(30) PATH '$.ts',
                   lat      NUMBER       PATH '$.lat',
                   lon      NUMBER       PATH '$.lon',
                   hr       NUMBER       PATH '$.heartRate',
                   speed    NUMBER       PATH '$.speed'
               )
           )
       ) j;
