# Báo cáo sơ bộ — Skeleton pipeline đã code + test

Trạng thái tại thời điểm này: **8 hàm trong `src/` đã có logic thật (không còn stub), có test pass cho từng hàm.** Toàn bộ chạy trên CPU, không cần GPU.

## 1. Đã code + test (chạy `python tests/test_*.py` để tự kiểm tra)

| Module | Hàm | Thư viện dùng | Test |
|---|---|---|---|
| `ingest.py` | `register_camera_source`, `read_frame` | OpenCV `VideoCapture` | `test_ingest.py` — đọc hết video, `None` khi hết, lỗi rõ nếu chưa đăng ký camera |
| `detection.py` | `detect_objects` | Ultralytics YOLOv8n (pretrained COCO) | `test_detection.py` — detect được person trên ảnh mẫu |
| `detection.py` | `detect_accident` | Rule tự viết (IOU va chạm + tụt tốc độ đột ngột), dùng `supervision.box_iou_batch` | `test_detection.py` — giả lập 2 xe va chạm, đúng thời điểm trigger |
| `tracking.py` | `update_tracks` | `supervision.ByteTrack` | `test_tracking.py` — track_id giữ nguyên qua nhiều frame |
| `features.py` | `extract_plate` | EasyOCR | `test_features.py` — đọc chữ trên ảnh biển số giả lập |
| `features.py` | `extract_face_embedding` | InsightFace (buffalo_l/ArcFace) | `test_features.py` — vector 512 chiều |
| `features.py` | `set_height_calibration`, `extract_pose_height` | MediaPipe Pose Landmarker | `test_features.py` — trả `None` nếu chưa calibrate |
| `calibration.py` | `set_calibration`, `pixel_to_world`, `world_to_pixel` | OpenCV homography | `test_calibration.py` — 2 chiều là nghịch đảo chính xác |
| `reid.py` | `match_person`, `register_person` | Cosine similarity tự viết (numpy) | `test_reid.py` |
| `storage.py` | `save_track`, `save_event` | sqlite3 (stdlib) | `test_storage.py` — đọc lại DB xác nhận đúng dữ liệu |
| `main.py` | `run_camera(camera_id, source)` | Nối 8 hàm trên thành 1 vòng lặp single-camera | `test_main.py` — mock từng bước, kiểm tra đúng thứ tự gọi + đúng dữ liệu lưu |
| `cross_camera.py` | `resolve_global_identity(track, frame)` | Ghép person track với global ID xuyên camera (face embedding + world_pos) | `test_cross_camera.py` — 2 track khác camera, cùng mặt → cùng global ID |

Package đã cài (`requirements.txt`): `supervision`, `ultralytics`, `mediapipe`, `easyocr`, `insightface`, `onnxruntime`.

Model đã tải về máy (dùng lại, không tải lại mỗi lần chạy):
- `yolov8n.pt` (6.3MB, project root)
- `models/pose_landmarker_lite.task` (5.6MB)
- EasyOCR models (~94MB, `~/.EasyOCR`)
- InsightFace buffalo_l (~601MB, `~/.insightface`)

## 2. Còn thiếu / chưa làm

Đã xử lý so với báo cáo trước:
- ✅ **Pipeline main** — `src/main.py` nối 8 hàm thành vòng lặp `ingest → detect → track → save track → (nếu tai nạn) features → save event`. Cần sửa 1 chỗ ở gốc để làm được: `Track` trước đây không giữ `class_id`, không phân biệt được track nào là xe/người — đã thêm field `class_id` vào `Track` và thread xuyên `tracking.py` (đã xác nhận `ByteTrack` giữ nguyên class qua các frame).
- ✅ **Cross-camera identity (Phase 4, bản rút gọn)** — `src/cross_camera.py::resolve_global_identity` ghép 1 person track với global ID xuyên camera bằng face embedding (tái dùng `features`+`reid`) và gắn `world_pos` nếu camera đã calibrate. Đây là building-block đúng, **chưa phải runner multi-thread chạy nhiều camera thật cùng lúc** (như `CrossCameraTracker` trong `noidung.txt`) — cố ý chưa làm vì chưa có ≥2 camera thật để test, làm giờ sẽ là scaffolding không kiểm chứng được.
- **Vehicle type** coi như đã có miễn phí: `main.py` dùng thẳng `class_id` từ YOLO (car/motorcycle/bus/truck) làm `VehicleInfo.vehicle_type`, không cần model classify riêng.
- ✅ **Dashboard (Phase 5)** — `src/api.py` (FastAPI: `GET /api/tracks`, `GET /api/events`, `WS /ws/events`, đọc thẳng sqlite hiện có) + `dashboard/` (React/Vite + Leaflet `CRS.Simple` cho world coordinates + panel cảnh báo nhận qua WebSocket). Đã seed dữ liệu mẫu, chạy `npm run dev` + mở Chrome thật để verify: map hiện đúng track, panel hiện đúng accident event, và **verify được cả real-time** — chèn 1 event mới vào DB trong lúc trang đang mở thì panel tự cập nhật không cần reload. Trong lúc verify phát hiện 1 bug thật (React StrictMode chạy effect 2 lần ở dev → marker bị nhân đôi) và đã sửa (`markersLayer.clearLayers()` trước khi vẽ lại).

- ✅ **Tool tune threshold** — tách `detect_accident` thành `accident_metrics()` (trả IOU/tốc độ thô) + threshold check riêng, và `scripts/tune_accident_thresholds.py` chạy pipeline trên 1 video, ghi CSV để đọc số chọn threshold. Chưa chạy trên video thật vì chưa có — chỉ mới test bằng mock.

Vẫn còn thiếu:
- **Threshold vẫn chưa được tune bằng số liệu thật** — cần chạy `scripts/tune_accident_thresholds.py <video>` trên video tai nạn thật khi có, rồi sửa 3 hằng số trong `src/detection.py`.
- **Vehicle color/brand** — chưa code, roadmap đã xếp ưu tiên thấp nhất, vẫn giữ nguyên quyết định đó.
- **Dashboard chưa có build/deploy thật** — mới chạy dev server (`npm run dev`) + `npm run build` để kiểm tra, chưa cấu hình serve bản production hay deploy lên đâu.

## 3. Đơn giản hoá có chủ đích — cần biết trước khi dùng thật (đánh dấu `ponytail:` trong code)

| Chỗ | Đang làm gì | Rủi ro nếu dùng thật luôn | Nâng cấp khi nào |
|---|---|---|---|
| `tracking.py` | Dùng `sv.ByteTrack` — **API này bị deprecate ở supervision 0.28, gỡ hẳn ở 0.30** (đang cài 0.29.1) | Nâng cấp `pip install -U supervision` sau này sẽ vỡ code | Pin `supervision<0.30` trong requirements, hoặc migrate khi supervision ra API thay thế chính thức |
| `detection.py` | `detect_accident` dùng `time.time()` làm mốc thời gian vì `Track` không mang timestamp của frame | Sai nếu xử lý lại video đã ghi (offline/batch) — chỉ đúng khi gọi ngay sau mỗi frame real-time | Thêm `timestamp` vào `Track`, hoặc truyền timestamp riêng vào `detect_accident` |
| `features.py` | `extract_pose_height` quy đổi pixel→cm bằng 1 hệ số cố định mỗi camera (`set_height_calibration`), không bù phối cảnh theo khoảng cách | Người đứng gần/xa camera cho ra chiều cao sai lệch khác nhau | Dùng `calibration.pixel_to_world` (ground-plane) + biết chiều cao/góc đặt camera thật để bù phối cảnh |
| `reid.py` | Embedding lưu trong RAM (dict Python) | Mất hết khi restart process, không chia sẻ được giữa nhiều tiến trình/server | Chuyển sang bảng DB (đã có `storage.py` làm nền) khi cần chạy nhiều process hoặc persist qua các lần restart |
| `storage.py` | Dùng sqlite3 (file `data/tracking.db`) thay Postgres/PostGIS thật | Không có GIS query, không tốt cho ghi đồng thời nhiều camera cùng lúc (sqlite lock cả file) | Chuyển Postgres+PostGIS khi có server thật (Phase 0 trong roadmap) — schema đã thiết kế tương thích |
| `calibration.py` | Homography 2D (mặt phẳng đường), không phải calibration 3D đầy đủ như `noidung.txt` mô tả | Không xử lý được độ dốc/gồ ghề mặt đường, chỉ đúng trên mặt phẳng phẳng | Đủ dùng cho giao thông đô thị bình thường; nâng cấp lên OpenCV `calibrateCamera` 3D chỉ khi mặt đường không phẳng |
| `src/api.py` | `WS /ws/events` đẩy event mới bằng poll DB mỗi 1s, không phải pub/sub thật | Alert có độ trễ tới 1s, tốn 1 kết nối DB mỗi giây/client | Chuyển sang message queue (Kafka/RabbitMQ, đã có trong roadmap Phase 0) khi nhiều client/nhiều camera |
| `src/api.py` | CORS mở `allow_origins=["*"]` | Ai cũng gọi được API từ browser bất kỳ domain nào | Siết lại origin cụ thể khi deploy thật (không phải chạy dev nữa) |

## 4. Tính năng mới: theo dõi người xuyên camera theo vị trí GIS (thay vì chỉ quanh tai nạn)

Đổi trọng tâm theo yêu cầu: không chỉ dùng cross-camera cho tai nạn, mà tìm 1 người bất kỳ sau khi họ rời khỏi camera A, dựa vào vị trí GIS + góc nhìn camera. 4 khối mới, đã code + test:

| Khối | File | Việc làm |
|---|---|---|
| 1. Đăng ký GIS camera | `src/camera_registry.py` | `register_camera(camera_id, lat, lng, facing_deg, fov_deg)` + `nearby_cameras(camera_id, radius_m, travel_bearing_deg=None)` — haversine + bearing, tự viết bằng `math` (không cần thư viện geo ngoài) |
| 2. `person_id` xuyên suốt | `models.Track` (+`person_id`, `timestamp`), `cross_camera.py`, `storage.py` | `resolve_global_identity` gán `person_id`+`embedding`+`world_pos` lên track; `storage.save_track` lưu cả `person_id`+`timestamp`; thêm `storage.find_person_sightings(person_id, camera_ids, since_timestamp)` |
| 3. Phát hiện rời camera | `tracking.departed_tracks(camera_id, current_tracks)` | So track_id đang active với lần gọi trước cùng camera, trả về track (kèm state cũ) nào vừa biến mất |
| 4. Truy vấn tìm kiếm | `src/person_search.py::search_departed_person(track, radius_m=500.0)` | Ghép khối 1+2+3: lấy camera gần camera vừa rời, tra sighting cùng `person_id` ở đó |

`main.py::run_camera` đã nối cả 4 khối: mỗi frame ghép `person_id` cho track người, lưu track, và khi phát hiện người rời khung hình thì tự gọi `search_departed_person` (hiện chỉ `print` kết quả, chưa có API/dashboard riêng cho việc này).

**Bug thật bắt được khi nối vào `main.py`:** `extract_face_embedding` (InsightFace) bị gọi 2 lần cho cùng 1 track/frame — 1 lần trong `resolve_global_identity` (để ghép person_id), 1 lần trong `_handle_accident` (để lưu `DriverInfo`). Test lộ ra qua `mock.assert_called_once_with` fail "Called 2 times". Đã sửa gốc: `resolve_global_identity` giờ lưu luôn `track.embedding`, `_handle_accident` đọc lại thay vì tính lại.

**Giới hạn cố ý (ponytail):**
- `search_departed_person` chỉ query DB tại đúng thời điểm rời camera — nếu chạy nhiều camera độc lập, camera gần đó có thể **chưa kịp ghi sighting** vào lúc query chạy (không có cơ chế chờ/poll lại). Cần runner thật chạy song song nhiều camera để biết cơ chế này có đủ dùng hay cần retry.

## 5. Đã làm thêm: lịch sử world_pos → travel_bearing, và map cấu hình camera GIS thật

- **`travel_bearing_deg`**: `cross_camera.py` giờ lưu 5 điểm `world_pos` gần nhất mỗi (camera_id, track_id), tính hướng di chuyển (độ, 0=Bắc/90=Đông, cùng quy ước với `camera_registry`) từ 2 điểm cuối, gán vào `track.travel_bearing_deg`. `person_search.search_departed_person` giờ truyền thẳng giá trị này vào `nearby_cameras` — camera đúng hướng nhưng quay lưng sẽ tự bị loại (test `test_travel_bearing_narrows_search_to_cameras_in_that_direction` xác nhận).
- **Camera đã persist xuống DB**: trước đó `camera_registry` chỉ sống trong RAM, mất khi restart. Thêm bảng `cameras` + `storage.save_camera`/`list_cameras`, và `api.py` hydrate `camera_registry` từ DB lúc khởi động — sửa xong trên dashboard giờ không mất khi restart backend.
- **Tab "Cameras" trên dashboard**: map OSM thật (không phải `CRS.Simple`), click để thêm camera tại đúng lat/lng, kéo marker để đổi vị trí, input số để chỉnh hướng nhìn/FOV, vẽ cone hình quạt biểu diễn góc nhìn, nút Lưu gọi `POST /api/cameras`. Đã verify bằng browser thật: thêm camera, zoom map, xác nhận cone vẽ đúng hướng Bắc khi facing_deg=0.

## 5b. Nâng cấp travel_bearing: dùng Kalman filter nội bộ của ByteTrack thay vì chỉ 2 điểm thô

Theo yêu cầu: expose vận tốc từ Kalman filter (`supervision.ByteTrack` đã có sẵn, dùng để dự đoán vị trí) thay vì tính hướng đi từ hiệu số 2 điểm `world_pos` gần nhất (nhạy nhiễu).

- **`tracking.predicted_velocity(camera_id, track_id)`** — đọc thẳng `STrack.mean[4:6]` (vx, vy tính bằng pixel/frame) từ Kalman filter nội bộ của ByteTrack, khớp qua `STrack.external_track_id` (đã verify bằng script thật: giá trị này chính là `tracker_id` mình vẫn dùng).
- **`cross_camera.py`**: `_bearing_from_kalman` dùng (vx,vy) này, chiếu qua `calibration.pixel_to_world` để tính hướng đi trong world-space (mượt hơn vì Kalman đã lọc nhiễu qua nhiều frame) — **ưu tiên dùng cách này**, chỉ fallback về `_bearing_from_history` (2 điểm world_pos thô) khi Kalman chưa có state (vd. track vừa xuất hiện, hoặc track đó không đi qua `tracking.update_tracks`).

**Bug thật bắt được khi viết test:** code đầu tiên dùng `track.travel_bearing_deg = _bearing_from_kalman(track) or _bearing_from_history(track)`. Khi hướng đi tính ra đúng **0.0° (hướng Bắc chính xác)** — một giá trị hợp lệ — Python coi `0.0` là falsy nên `or` tự động rơi xuống fallback (trả `None` vì chưa đủ history), làm mất luôn kết quả đúng. Sửa bằng so sánh `is not None` rõ ràng thay vì `or`. Đây là loại bug rất dễ lọt qua review vì code "trông đúng" và chỉ lộ ra khi giá trị hợp lệ tình cờ là 0.

## 6. Việc cần bạn quyết định

1. ~~Pin `supervision<0.30`~~ — xong.
2. ~~Viết `main.py` nối pipeline~~ — xong.
3. ~~Dashboard Phase 5~~ — xong (React+Leaflet+WebSocket), verify bằng browser thật.
4. ~~Theo dõi người theo GIS (4 khối)~~ — xong.
5. ~~travel_bearing từ lịch sử world_pos~~ — xong (mục 5).
6. ~~Map cấu hình camera GIS (kéo vị trí, chỉnh hướng nhìn/FOV)~~ — xong (mục 5), đã persist DB.
7. ~~Module "xem camera → click chọn người → tự theo dõi"~~ — xong (mục 7 bên dưới), dùng WebRTC theo lựa chọn của bạn.
8. **Có camera/video thật để chạy `run_camera()`/Live view end-to-end không?** Hiện chỉ test bằng ảnh/video giả lập + mock/demo video lặp lại, chưa chạy trên dữ liệu thật.
9. **Có đồng ý dùng sqlite tạm thời, hay cần Postgres thật ngay từ đầu?** (ảnh hưởng `storage.py` và `src/api.py`)
10. **Cách chạy dashboard hiện tại:** `python -m uvicorn src.api:app --port 8000` (backend) + `cd dashboard && npm run dev` (frontend, mặc định port 5173) — cả 2 đang tắt sau khi verify xong, cần bật lại thủ công khi muốn xem.

## 7. Module "xem camera → click chọn người → tự theo dõi" — đã xong (WebRTC)

Theo lựa chọn của bạn: demo bằng video file lặp lại + stream qua **WebRTC** (không phải MJPEG như tôi đề xuất ban đầu).

- **`src/webrtc_stream.py`**: `CameraTrack` (subclass `aiortc.VideoStreamTrack`) chạy detect+track+ghép person_id **mỗi frame thật** (không phải giả lập), đẩy bbox/class_id/person_id qua WebRTC DataChannel song song với video. `build_answer()` xử lý SDP offer/answer (signaling qua 1 HTTP request, không cần signaling server riêng).
- **`POST /webrtc/offer`** trong `api.py`: nhận offer từ browser, trả answer.
- **`dashboard/src/LiveView.jsx`**: `<video>` nhận stream WebRTC + `<canvas>` overlay vẽ bbox từ DataChannel, click vào người → chọn `person_id` → highlight đỏ + nút "Tìm ở camera khác" gọi `GET /api/persons/{id}/sightings` (tái dùng `camera_registry`+`storage.find_person_sightings` có sẵn, không có logic mới).
- Test: `tests/test_webrtc_stream.py` dùng **client WebRTC thật** (aiortc phía test đóng vai browser) để đàm phán SDP thật, nhận video frame thật + metadata thật qua DataChannel — không mock phần lõi WebRTC.

**Verify bằng browser thật (Chrome) — bắt được 3 bug thật trong lúc test, cả 3 đã sửa:**

| # | Bug | Nguyên nhân | Sửa |
|---|---|---|---|
| 1 | Video không lặp lại được, cứ hết video là đứng hình / crash ngầm | `register_camera_source` gọi lại **không** mở lại `cv2.VideoCapture` (chỉ cập nhật `_sources`, không đụng `_captures` đã có sẵn) — dùng để "loop" là sai | Thêm `ingest.reset_camera(camera_id)` (đóng + xoá capture cũ, `read_frame` lần sau tự mở capture mới) |
| 2 | Click vào người không chọn được, cứ chọn nhầm sang xe/nền phía sau | Nhiều bbox chồng nhau tại 1 điểm (người đứng trước xe bus to) — code cũ dùng `.find()` lấy phần tử **đầu tiên khớp** trong mảng, không quan tâm bbox nào cụ thể hơn | Đổi sang lấy bbox **diện tích nhỏ nhất** trong các bbox khớp tại điểm click |
| 3 | "Tìm ở camera khác" luôn trả về rỗng | `CameraTrack.recv()` (WebRTC) chưa gọi `storage.save_track` — track thấy trên Live view chưa từng được ghi vào DB nên không có gì để tra | Thêm `storage.save_track(track)` vào `CameraTrack.recv()`, giống `main.py` đã làm |

**Giới hạn cố ý (ponytail):**
- Inference (YOLO + InsightFace) chạy CPU mỗi frame → không đạt tốc độ video thật (30fps), có độ trễ vài trăm ms đến vài giây/frame tuỳ độ phân giải. Đủ dùng để xem+chọn người, không phải giám sát real-time tốc độ cao.
- "Theo dõi" hiện chỉ là **highlight cùng person_id trong cùng 1 camera đang xem** + nút tra cứu thủ công sang camera khác — chưa tự động chuyển sang xem stream của camera khác khi người đó xuất hiện ở đó.

## 8. Tích hợp sang Báo Tin (2026-07-23) — CHỈ phần phát hiện tai nạn + OCR biển số

Anh yêu cầu đưa hệ thống này vào app cán bộ của dự án "Báo Tin" (`D:\App\BaoTin`) dưới dạng
tab "Cảnh báo tai nạn giao thông". Đã từ chối phần nhận diện/theo dõi người xuyên camera
(`reid.py`, `cross_camera.py`, `person_search.py`, `features.extract_face_embedding`) — đúng
như cảnh báo pháp lý đã ghi ở `roadmap.md` mục 2 ("cần xác nhận cơ sở pháp lý... trước khi
lưu trữ lâu dài"). Anh xác nhận đây là quyết định của anh trên dự án của anh và yêu cầu dừng
tranh luận — ghi lại ở đây để phiên sau biết bối cảnh, không phải để tranh luận lại.

Đã làm, CHỈ dùng `ingest.py` + `detection.py` + `features.extract_plate` (không đụng gì tới
nhận diện người):
- `scripts/traffic_accident_alert_worker.py` (mới): vòng lặp giống `main.py`'s `run_camera`
  nhưng bỏ hết phần `cross_camera`/`storage`(sqlite)/`person_search`/pose height/face
  embedding. Khi `detection.detect_accident()` = True (có cooldown 30s tránh spam), OCR biển
  số các track class xe rồi `POST` tới `{backend_url}/detections/traffic-accidents` của
  Báo Tin (multipart: `cameraId`, `plateNumbers`, `thumbnail` = 1 frame JPEG).
- Test `tests/test_traffic_accident_alert_worker.py` — mock `features.extract_plate` +
  `requests.post`, không cần chạy YOLO thật hay có backend thật đang chạy.
- Thêm `requests` vào `requirements.txt` (chưa có, cần cho HTTP POST).
- Phía Báo Tin: bảng `traffic_accident_alerts` mới (không đụng bảng `reports`/`cameras` cũ),
  service/routes/tests riêng, tab mới trong `mobile-app-officer`. Chi tiết xem
  `docs/NHATKY_2026-07-23.md` của Báo Tin (không phải file này).

**Cách chạy demo:** `python scripts/traffic_accident_alert_worker.py <camera-id-thật> --video
video.mp4 --backend-url https://baotin.work.gd/api --api-key <TRAFFIC_DETECTOR_API_KEY>` —
dùng `video.mp4` mẫu có sẵn (lặp lại khi hết), không phải RTSP camera thật, đúng quy ước "demo
dùng seed data" của Báo Tin.

**Chưa làm / cần biết:**
- Chưa chạy thật với `video.mp4` của repo này để xem `detect_accident()` có thật sự bắt được
  gì trong đó không — threshold (`_COLLISION_IOU_THRESHOLD=0.75`) mới tune trên video giao
  thông đông đúc khác (xem comment trong `detection.py`), chưa chắc đúng cho video này.
- `--camera-id` phải là id thật trong bảng `cameras` của Báo Tin (lấy từ DB, ví dụ 1 trong 3
  camera demo ở `seed-cameras.ts`) — chưa có cách tra cứu id này từ script, phải query DB
  thủ công.

## 9. Tối ưu tốc độ xử lý real-time + đóng gói app Windows (2026-07-23)

Mục tiêu: pipeline gốc chỉ ~1.2 fps trên `video.mp4` (842 frame, nguồn 30fps) — không đạt
real-time. Sau 1 phiên tối ưu liên tục đo-sửa-đo lại: **~58.5 fps ổn định** (không tính lúc
có tai nạn), tức nhanh gấp **~49 lần**.

**Bug thật bắt được (không phải chỉ đoán rồi sửa):**

| # | Bug | Cách phát hiện | Sửa |
|---|---|---|---|
| 9 | `storage._get_connection()` có logic check cache ở đầu hàm nhưng **quên gán `_connection`/`_connection_path` trước khi return** → mỗi `save_track` vẫn mở connection mới + chạy lại `CREATE TABLE IF NOT EXISTS` + `PRAGMA table_info` mỗi lần, y hệt bug gốc dù tưởng đã sửa | Benchmark trước/sau không khớp dự đoán toán học → thêm counter đếm số lần "tạo connection mới" mới lộ ra | Thêm 2 dòng gán còn thiếu |
| 10 | SQLite mặc định fsync đĩa mỗi `commit()` (rollback journal mode) → mỗi track ghi tốn ~500ms | Benchmark tách riêng từng bước lộ ra `save_track` chiếm 60-87% thời gian | `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` — nhanh hơn ~65 lần, chấp nhận rủi ro mất vài transaction cuối nếu mất điện đúng lúc (không hỏng DB) |
| 11 | `cross_camera.resolve_global_identity` (face embedding InsightFace) chạy mỗi frame cho mọi track người, kể cả khi hoàn toàn không cần (video giao thông, không cần ghép person_id liên tục) | Benchmark tách bước lộ `resolve_identity` chiếm ~30% | `main.py`: chỉ gọi khi có tai nạn thật (`_handle_accident`), không phải mỗi frame. `cross_camera.py`: thêm rate-limit nội bộ (`_FACE_EMBED_INTERVAL=5`) cho chỗ vẫn cần liên tục (`webrtc_stream.py`, tính năng click-chọn-người) |
| 12 | `webrtc_stream.py::CameraTrack.recv()` là `async def` nhưng thân hàm 100% đồng bộ (YOLO+tracking+DB+face embedding) → block toàn bộ event loop FastAPI mỗi frame, đo thực tế treo tới **585ms/frame** | Test đo độ trễ 1 coroutine `ticker()` chạy song song trong lúc `recv()` xử lý | Chuyển phần xử lý đồng bộ vào `asyncio.to_thread` — độ trễ tối đa còn **27ms** |
| 13 | `webrtc_stream.py` chưa được áp frame-skip detection (chỉ `main.py` có) → live view giật hình vì detect không theo kịp nhịp phát ~30fps cố định của aiortc | User báo trực tiếp "giật hình, không thấy 50fps" | Áp cùng logic frame-skip (`_DETECT_INTERVAL`, `_extrapolate_tracks` dùng lại từ `main.py`) |
| 14 | `torch` cài mặc định là bản CPU-only dù máy có GPU thật (GTX 1080) — sau khi cài lại bản CUDA đúng, gặp tiếp: bản `cu130` mới nhất **bỏ hỗ trợ kiến trúc Pascal** (GPU đời 2016), phải hạ xuống `cu126` | `torch.cuda.is_available()` không đủ tin — chạy thử 1 phép tính thật trên GPU mới lộ ra kernel không tồn tại cho compute capability đó | `detection.py::_select_device()` — không chỉ tin `is_available()`, thử chạy 1 op nhỏ thật trên `cuda`, lỗi thì tự fallback `cpu`. Tự thích ứng máy khác (RTX 5090, v.v.) mà không cần sửa code |

**Frame-skip detection (đòn bẩy lớn nhất, 16fps → 58.5fps):** `main.py`/`webrtc_stream.py` chỉ
chạy YOLO thật mỗi `_DETECT_INTERVAL=2` frame; frame giữa ngoại suy bbox bằng vận tốc Kalman
nội bộ của ByteTrack (`tracking.predicted_velocity`, hàm có sẵn, không đổi signature).
Đánh đổi: vị trí ở frame ngoại suy là ước lượng tuyến tính, sai số tăng nếu vật thể đổi hướng
đột ngột giữa 2 lần detect thật — chấp nhận được vì interval nhỏ (tối đa 1 frame nội suy).

**Đóng gói thành app Windows (Electron):** thư mục `electron/` mới — `main.js` tự spawn
`python -m uvicorn src.api:app` làm backend, mở cửa sổ desktop load `http://127.0.0.1:8000`
(FastAPI giờ tự serve luôn `dashboard/dist` đã build qua `StaticFiles`, gộp 1 process thay vì
2). Build ra installer thật (`npm run dist` trong `electron/`) →
`electron/dist_installer/App Add-in Setup 1.0.0.exe` (~78MB, NSIS) — đã cài thử bằng `/S`
(silent) vào `C:\Program Files\App Add-in\`, có Start Menu shortcut, chạy đúng từ vị trí cài
thật (không phải bản portable). Cần bật Windows Developer Mode 1 lần trên máy dev để build
NSIS (electron-builder cần quyền tạo symbolic link khi giải nén tool ký code).

**Giới hạn cố ý (ponytail) — cần biết trước khi dùng thật:**
- Backend vẫn cần Python + toàn bộ dependency (`torch`, `ultralytics`, `insightface`,
  `mediapipe`, `easyocr`...) cài sẵn trên máy chạy app — **không phải installer
  dependency-free** (Electron chỉ spawn Python có sẵn, không bundle Python runtime). Muốn
  chạy trên máy sạch không có Python phải đóng gói kiểu khác (PyInstaller, nặng hơn nhiều,
  chưa làm vì user chỉ chọn hướng Electron).
- Đóng cửa sổ bình thường (nút X / quit) → backend tự tắt sạch (`stopBackend()` đã code).
  Nhưng **force-kill qua Task Manager** có thể để lại process Python mồ côi (Windows không tự
  tie lifetime process con vào process cha như POSIX) — gặp đúng trường hợp này lúc test, phải
  tắt tay. Fix triệt để cần Windows Job Object, chưa làm.
- GPU: chỉ auto-detect CUDA→CPU (NVIDIA). Chưa làm DirectML cho AMD/đa nền tảng — user chưa
  có phần cứng AMD thật để test, cố ý hoãn tới khi có máy thật thay vì ship code không kiểm
  chứng được.
- `data/tracking.db` hiện có nhiều dữ liệu test/benchmark (`bench_cam`, `bench_realtime*`,
  `perf_probe*`, nhiều accident event giả do threshold dễ trigger lúc test lặp) — user đã xác
  nhận **không cần xoá**, để nguyên.
