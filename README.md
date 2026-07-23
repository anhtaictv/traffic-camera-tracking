# Traffic Camera Tracking

🇻🇳 [Tiếng Việt](README.vi.md) · 🇬🇧 English (this file)

Traffic-camera pipeline that detects accidents in real time, reads vehicle plates, and can
re-identify a person across multiple cameras using real GIS positions. Ships as a Python
backend + React dashboard, and can be packaged into a standalone Windows desktop app.

## What it does

- **Object detection & tracking** — YOLOv8 (person/car/motorcycle/bus/truck) + ByteTrack,
  per camera.
- **Accident detection** — collision (IoU) + sudden-deceleration rule on top of tracked boxes.
- **Plate OCR** — reads vehicle plates (EasyOCR) when an accident is detected.
- **Cross-camera person tracking** — matches a person across cameras by face embedding
  (InsightFace) + real GIS position/bearing, so you can search "where did this person show up
  next" after they leave a camera's view.
- **Live dashboard** (React + Leaflet) — 3 tabs: live tracking map + accident alerts
  (WebSocket), camera GIS configuration (OpenStreetMap), and a live WebRTC view where you can
  click a person to follow them and jump to where they were seen elsewhere.
- **Windows desktop app** (Electron) — wraps the backend + dashboard into a single installable
  app; no terminal or browser needed.

## Performance

Optimized from ~1.2 fps to **~58 fps steady-state** on a single stream (GPU auto-detected,
YOLO only runs on every other frame, bbox is extrapolated in between using the tracker's own
Kalman velocity). See `report.md` §9 for the full before/after breakdown and the actual bugs
that were fixed to get there (not just parameter tuning).

## Tech stack

- **Backend:** Python, FastAPI, Ultralytics YOLOv8, `supervision` (ByteTrack), InsightFace,
  EasyOCR, MediaPipe, aiortc (WebRTC), SQLite (WAL mode)
- **Dashboard:** React (Vite), Leaflet/OpenStreetMap
- **Desktop packaging:** Electron + electron-builder (NSIS installer)

## Quick start

```bash
# Backend
pip install -r requirements.txt
python -m uvicorn src.api:app --port 8000

# Dashboard (dev mode)
cd dashboard && npm install && npm run dev   # http://localhost:5173
```

Or run everything as one desktop app:

```bash
cd dashboard && npm run build     # build dashboard -> served by the backend
cd electron && npm install
cd electron && npm start          # dev
cd electron && npm run dist       # -> electron/dist_installer/App Add-in Setup *.exe
```

## Standalone scripts (no dashboard needed)

- `scripts/draw_person_path.py <person_id> --output path.html` — draws a person's real-world
  path on an OpenStreetMap HTML file.
- `scripts/tune_accident_thresholds.py <video> --output out.csv` — runs the pipeline on a real
  video and logs collision/speed numbers to help pick accident-detection thresholds from data.

## Tests

```bash
for f in tests/test_*.py; do python "$f"; done
```

## Known limitations

- SQLite instead of PostgreSQL/PostGIS for now — fine at current scale.
- Accident-detection thresholds are tuned on sample traffic footage, not verified real
  accident video yet.
- The desktop app still needs Python + dependencies installed on the machine it runs on — it's
  not a dependency-free installer.
- GPU support is NVIDIA/CUDA auto-detect only; no AMD/DirectML path yet (untested, no AMD
  hardware available).

Full architecture table, function-by-function status, and every real bug found + fixed during
development: see `CLAUDE.md` and `report.md`. Current-state summary: `SUMMARY.md`.
