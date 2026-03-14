from pathlib import Path
import csv
import fitdecode
from datetime import datetime

# Path logic for script in "src/", data in "data/"
ROOT_DIR = Path(__file__).resolve().parent.parent
FIT_DIR = ROOT_DIR / "data" / "fit"
OUT_DIR = ROOT_DIR / "data"

# Added "filename" as the first column
COLUMNS = [
    "filename", "ts", "latitude", "longitude", "altitude", 
    "heart_rate", "power", "cadence", "speed", "temperature", "distance"
]

def get_start_date(fit_path: Path) -> str:
    try:
        with fitdecode.FitReader(str(fit_path)) as fit:
            for frame in fit:
                if isinstance(frame, fitdecode.FitDataMessage):
                    ts = frame.get_value("timestamp", fallback=None)
                    if isinstance(ts, datetime):
                        return ts.strftime("%Y_%m_%d")
    except: pass
    return "0000_00_00"

def convert(fit_path: Path, csv_path: Path) -> int:
    rows = 0
    fname = csv_path.name  # This is the value for the first column
    
    with (
        fitdecode.FitReader(str(fit_path)) as fit,
        open(csv_path, "w", newline="", encoding="utf-8") as f,
    ):
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(COLUMNS)

        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage) or frame.name != "record":
                continue

            def get_val(name):
                try:
                    f_val = frame.get_field(name)
                    return f_val.value if f_val else None
                except: return None

            ts = get_val("timestamp")
            lat = get_val("position_lat")
            lon = get_val("position_long")
            alt = get_val("enhanced_altitude") or get_val("altitude")
            spd = get_val("enhanced_speed") or get_val("speed")
            dist = get_val("distance")
            temp = get_val("temperature") or get_val("ambient_temperature")

            row = [
                fname, # Column 1: Filename
                ts.strftime("%Y-%m-%dT%H:%M:%S.000Z") if ts else "",
                round(lat * (180 / 2**31), 12) if lat else "",
                round(lon * (180 / 2**31), 12) if lon else "",
                round(alt, 1) if alt else "",
                get_val("heart_rate") or "",
                get_val("power") or "",
                get_val("cadence") or "",
                round(spd * 3.6, 3) if spd else "",
                temp if temp else "",
                round(dist / 1000, 5) if dist else "",
            ]
            writer.writerow(row)
            rows += 1
    return rows

def main():
    if not FIT_DIR.exists(): return
    
    for fp in sorted(FIT_DIR.glob("*.fit")):
        prefix = get_start_date(fp)
        # Clean filename: no spaces or brackets
        clean_name = fp.with_suffix(".csv").name.replace(" ", "_").replace("(", "").replace(")", "")
        final_name = f"{prefix}_{clean_name}"
        csv_path = OUT_DIR / final_name
        
        count = convert(fp, csv_path)
        print(f"Processed: {final_name} ({count} rows)")

if __name__ == "__main__":
    main()