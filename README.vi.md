# Traffic Camera Tracking

🇻🇳 Tiếng Việt (file này) · 🇬🇧 [English](README.md)

Hệ thống giám sát camera giao thông: phát hiện tai nạn real-time, đọc biển số xe, và theo dõi
1 người xuyên nhiều camera dựa trên vị trí GIS thật. Gồm backend Python + dashboard React, có
thể đóng gói thành app desktop Windows độc lập.

## Làm được gì

- **Nhận diện + theo dõi vật thể** — YOLOv8 (người/ô tô/xe máy/xe buýt/xe tải) + ByteTrack,
  theo từng camera.
- **Phát hiện tai nạn** — rule va chạm (IOU) + giảm tốc đột ngột trên track đã theo dõi.
- **OCR biển số** — đọc biển số xe (EasyOCR) khi phát hiện tai nạn.
- **Theo dõi người xuyên camera** — ghép 1 người qua nhiều camera bằng face embedding
  (InsightFace) + vị trí/hướng đi GIS thật, tra được "người này xuất hiện tiếp ở đâu" sau khi
  rời khỏi 1 camera.
- **Dashboard trực tiếp** (React + Leaflet) — 3 tab: map theo dõi + cảnh báo tai nạn real-time
  (WebSocket), cấu hình vị trí GIS camera (OpenStreetMap), và xem live qua WebRTC — click vào
  1 người để chọn theo dõi, tra xem người đó từng xuất hiện ở camera nào khác.
- **App desktop Windows** (Electron) — gộp backend + dashboard thành 1 app cài đặt được, không
  cần mở terminal hay trình duyệt thủ công.

## Tốc độ xử lý

Đã tối ưu từ ~1.2 fps lên **~58 fps ổn định** trên 1 luồng camera (tự nhận GPU, YOLO chỉ chạy
mỗi 2 frame, frame giữa nội suy bbox bằng vận tốc Kalman có sẵn của tracker). Chi tiết trước/sau
từng bước + các bug thật đã sửa (không chỉ chỉnh tham số) xem `report.md` mục 9.

## Công nghệ dùng

- **Backend:** Python, FastAPI, Ultralytics YOLOv8, `supervision` (ByteTrack), InsightFace,
  EasyOCR, MediaPipe, aiortc (WebRTC), SQLite (chế độ WAL)
- **Dashboard:** React (Vite), Leaflet/OpenStreetMap
- **Đóng gói desktop:** Electron + electron-builder (installer NSIS)

## Chạy nhanh

```bash
# Backend
pip install -r requirements.txt
python -m uvicorn src.api:app --port 8000

# Dashboard (dev mode)
cd dashboard && npm install && npm run dev   # http://localhost:5173
```

Hoặc chạy gộp thành 1 app desktop:

```bash
cd dashboard && npm run build     # build dashboard -> backend tự serve luôn
cd electron && npm install
cd electron && npm start          # chạy dev
cd electron && npm run dist       # -> electron/dist_installer/App Add-in Setup *.exe
```

## Script độc lập (không cần dashboard)

- `scripts/draw_person_path.py <person_id> --output path.html` — vẽ lộ trình thật của 1 người
  lên bản đồ OpenStreetMap (file HTML standalone).
- `scripts/tune_accident_thresholds.py <video> --output out.csv` — chạy pipeline trên video
  thật, ghi số liệu va chạm/tốc độ để chọn threshold phát hiện tai nạn dựa trên số liệu.

## Chạy test

```bash
for f in tests/test_*.py; do python "$f"; done
```

## Giới hạn hiện tại

- Dùng SQLite thay Postgres/PostGIS tạm thời — đủ dùng ở quy mô hiện tại.
- Threshold phát hiện tai nạn mới tune trên video giao thông mẫu, chưa xác thực bằng video tai
  nạn thật.
- App desktop vẫn cần máy chạy đã cài sẵn Python + dependency — chưa phải installer
  dependency-free.
- Chỉ auto-detect GPU NVIDIA/CUDA, chưa có đường AMD/DirectML (chưa có phần cứng AMD để test).

Bảng kiến trúc đầy đủ, trạng thái từng hàm, và toàn bộ bug thật đã bắt được + sửa trong quá
trình code: xem `CLAUDE.md` và `report.md`. Tổng quan trạng thái hiện tại: `SUMMARY.md`.
