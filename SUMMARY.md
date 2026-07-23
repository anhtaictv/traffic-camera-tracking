# Tổng kết hệ thống — đã code những gì

Hệ thống giám sát/theo dõi người & xe qua camera: phát hiện tai nạn, nhận diện đặc điểm xe/người, và theo dõi 1 người xuyên nhiều camera dựa trên vị trí GIS thật. Chạy được trên CPU, tự dùng GPU (NVIDIA/CUDA) nếu máy có — auto-detect, fallback CPU nếu không khớp. Có test cho từng hàm. Đóng gói được thành app Windows desktop (Electron, xem mục 8).

## 1. Pipeline lõi (1 camera)

| Module | Việc làm |
|---|---|
| `src/ingest.py` | Đọc frame từ video/RTSP (`read_frame`), lặp lại video khi hết (`reset_camera`) |
| `src/detection.py` | YOLOv8 detect người/xe (`detect_objects`), rule phát hiện va chạm+giảm tốc (`accident_metrics`, `detect_accident`) |
| `src/tracking.py` | Theo dõi 1 camera bằng ByteTrack (`update_tracks`), phát hiện track vừa biến mất (`departed_tracks`), expose vận tốc Kalman filter nội bộ (`predicted_velocity`) |
| `src/features.py` | OCR biển số, embedding khuôn mặt (InsightFace), ước lượng chiều cao (MediaPipe Pose) |
| `src/main.py` | `run_camera()` — nối toàn bộ pipeline trên thành 1 vòng lặp cho 1 camera |

## 2. Theo dõi người xuyên camera theo vị trí GIS

| Module | Việc làm |
|---|---|
| `src/calibration.py` | Quy đổi pixel ↔ tọa độ mặt phẳng đường (world_pos, mét) trong 1 camera, qua homography |
| `src/camera_registry.py` | Vị trí GIS (lat/lng) + góc nhìn thật của từng camera; tìm camera nào gần nhau (`nearby_cameras`, theo khoảng cách + hướng di chuyển); quy đổi world_pos cục bộ sang lat/lng thật (`local_to_latlng`) |
| `src/cross_camera.py` | Ghép 1 person track với global `person_id` xuyên camera (face embedding), tính `travel_bearing_deg` (hướng đi) — ưu tiên vận tốc từ Kalman filter, fallback lịch sử vị trí thô khi chưa đủ dữ liệu |
| `src/person_search.py` | Khi 1 người rời khỏi camera A: tìm camera GIS gần đó đúng hướng đang đi, tra xem người đó đã xuất hiện ở đâu |
| `src/storage.py` | Lưu track/sự kiện xuống sqlite, tự vá schema nếu DB cũ thiếu cột, truy vấn lịch sử theo person_id |

## 3. Dashboard (React + FastAPI) — `dashboard/` + `src/api.py`

3 tab:
- **Tracking** — map phẳng xem track hiện tại + panel cảnh báo tai nạn real-time (WebSocket)
- **Cameras** — map GIS thật (OpenStreetMap), click thêm camera, kéo marker đổi vị trí, chỉnh hướng nhìn/FOV, lưu xuống DB
- **Live** — xem video camera qua WebRTC (chạy detect+track+nhận diện thật mỗi frame), **click vào 1 người để chọn theo dõi**, highlight người đó, nút tra cứu xem người đó từng xuất hiện ở camera nào khác

## 4. Module độc lập — `scripts/`

Không cần dashboard/FastAPI, chỉ cần Python:

| Script | Việc làm | Cách chạy |
|---|---|---|
| `draw_person_path.py` | **Vẽ lộ trình 1 người lên bản đồ thật** (OpenStreetMap, không cần API key) — điểm bắt đầu (xanh), kết thúc (đỏ), đường đi, mũi tên hướng đi hiện tại | `python scripts/draw_person_path.py <person_id> --output path.html` rồi mở file HTML bằng browser |
| `tune_accident_thresholds.py` | Chạy pipeline trên 1 video thật, ghi CSV số liệu va chạm/tốc độ để tự chọn threshold `detect_accident` thay vì đoán | `python scripts/tune_accident_thresholds.py <video> --output out.csv` |

## 5. Bug thật bắt được khi test (không phải chỉ viết code suông)

| # | Bug | Cách phát hiện | Sửa |
|---|---|---|---|
| 1 | `extract_face_embedding` (InsightFace) gọi 2 lần cho cùng 1 track/frame | Test `mock.assert_called_once` báo "called 2 times" | Tái dùng embedding đã tính, không gọi lại |
| 2 | Dashboard vẽ marker nhân đôi trên map (React StrictMode chạy effect 2 lần) | Verify bằng browser thật, đếm marker | `clearLayers()` trước khi vẽ lại |
| 3 | Video không lặp lại được khi hết (WebRTC live view bị đứng hình) | Verify bằng browser thật | `ingest.reset_camera()` đóng & mở lại capture đúng cách |
| 4 | Click chọn người trên Live view luôn trúng nhầm xe/nền phía sau | Verify bằng browser thật + console log giá trị thật | Chọn box diện tích nhỏ nhất trong các box chồng nhau, không lấy box đầu tiên |
| 5 | "Tìm ở camera khác" luôn trả về rỗng | Verify bằng browser thật | Live view thiếu `storage.save_track()`, đã bổ sung |
| 6 | Hướng đi tính ra đúng 0.0° (hướng Bắc) bị mất — rơi về fallback sai | Viết test cho giá trị 0.0 cụ thể | `0.0 or x` bị Python coi falsy → đổi thành so sánh `is not None` |
| 7 | DB thật lỗi "no such column: person_id" khi chạy `draw_person_path.py` | Chạy script thật trên `data/tracking.db` có sẵn | Thêm `_ensure_column()` tự vá schema thiếu cột thay vì chỉ xoá file DB |
| 8 | Script crash `UnicodeEncodeError` khi in tiếng Việt trên console Windows | Chạy script thật | `sys.stdout.reconfigure(encoding="utf-8")` |

## 6. Giới hạn cố ý — cần biết trước khi dùng thật

- **sqlite tạm thay Postgres/PostGIS** — đủ dùng ở quy mô hiện tại, nâng cấp khi có hạ tầng DB thật.
- **`WS /ws/events` poll DB mỗi 1s**, không phải pub/sub thật — đủ cho 1 dashboard, cần message queue khi nhiều client/camera.
- ~~Inference (YOLO+InsightFace) chạy CPU mỗi frame — không đạt tốc độ video thật~~ **đã tối ưu (2026-07-23)**: GPU auto-detect + frame-skip detection (chỉ YOLO thật mỗi 2 frame, nội suy Kalman ở giữa) + sửa bug DB (WAL + connection reuse) → ~58fps ổn định, vượt tốc độ video nguồn (30fps). Xem mục 8 và `report.md` mục 9 để biết chi tiết + giới hạn còn lại (chưa hỗ trợ GPU AMD, backend vẫn cần Python cài sẵn).
- **`detect_accident` threshold (IOU>0.1, giảm tốc<30%) chưa tune bằng tai nạn thật** — có sẵn tool (`tune_accident_thresholds.py`) để làm việc này khi có video thật.
- **`local_to_latlng` giả định gốc tọa độ local trùng vị trí GIS của camera** — đúng nếu calibration được set up theo quy ước này; cần biết khi thêm camera mới.
- **`person_search.search_departed_person` chỉ query đúng lúc rời camera** — nếu các camera chạy độc lập, camera gần đó có thể chưa kịp ghi dữ liệu; chưa có cơ chế chờ/retry.

## 7. Cách chạy nhanh

```bash
# Cài dependency
pip install -r requirements.txt
cd dashboard && npm install

# Chạy dashboard đầy đủ
python -m uvicorn src.api:app --port 8000     # backend
cd dashboard && npm run dev                    # frontend (port 5173)

# Vẽ lộ trình 1 người (module độc lập, không cần server)
python scripts/draw_person_path.py 7 --output path.html

# Tune threshold phát hiện tai nạn trên video thật
python scripts/tune_accident_thresholds.py video.mp4 --output tune.csv

# Chạy toàn bộ test
for f in tests/test_*.py; do python "$f"; done
```

## 8. App Windows desktop (Electron) — `electron/`

Đóng gói backend (FastAPI, tự serve luôn `dashboard/dist` đã build) + dashboard thành 1 app desktop thật, không cần mở terminal/browser thủ công:

```bash
cd dashboard && npm run build          # build dashboard -> dashboard/dist (chỉ cần lại khi sửa dashboard)
cd electron && npm install             # 1 lần
cd electron && npm start               # chạy dev (mở cửa sổ desktop ngay)
cd electron && npm run dist            # đóng gói installer .exe (electron/dist_installer/App Add-in Setup 1.0.0.exe)
```

Đã verify: cài `/S` (silent) vào `C:\Program Files\App Add-in\`, có Start Menu shortcut, chạy đúng — tự spawn backend Python, mở cửa sổ load dashboard. Giới hạn: máy chạy app vẫn cần cài sẵn Python + dependency (`requirements.txt`) — không phải installer dependency-free.

Chi tiết đầy đủ hơn (quyết định cần chốt, lịch sử thay đổi từng bước, các bug thật đã sửa): xem `report.md`. Quy tắc code bắt buộc bám theo: xem `CLAUDE.md`.
