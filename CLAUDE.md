CLAUDE.md
Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## 5. Kiến trúc pipeline (bắt buộc bám theo khi code)

Khung sườn đã có sẵn trong `src/`. Khi code bất kỳ phần nào của hệ thống, PHẢI dùng đúng các hàm/model dưới đây — không tạo hàm trùng chức năng, không đổi tên/signature đã định nghĩa. Nếu cần hàm mới ngoài danh sách này, dừng lại và hỏi trước.

| File | Hàm | Trách nhiệm | Trạng thái |
|---|---|---|---|
| `src/models.py` | `Frame`, `Detection`, `Track` (có `class_id`, `person_id`, `timestamp`, `travel_bearing_deg`), `VehicleInfo`, `DriverInfo`, `AccidentEvent` | Data model dùng chung xuyên toàn bộ pipeline | ✅ done |
| `src/ingest.py` | `register_camera_source(camera_id, source)`, `read_frame(camera_id)`, `reset_camera(camera_id)` | Đăng ký nguồn video + lấy frame kế tiếp (cv2.VideoCapture) + đóng/mở lại capture (lặp video khi hết) | ✅ done + test |
| `src/detection.py` | `detect_objects(frame)`, `accident_metrics(tracks)`, `detect_accident(tracks)` | YOLOv8 detect person/car/... + IOU va chạm/tốc độ thô (`accident_metrics`) + rule quyết định (`detect_accident` dùng threshold trên `accident_metrics`) | ✅ done + test |
| `src/tracking.py` | `update_tracks(camera_id, detections)`, `departed_tracks(camera_id, current_tracks)`, `predicted_velocity(camera_id, track_id)` | Tracker 1-camera (`supervision.ByteTrack`) + phát hiện track vừa biến mất + expose (vx,vy) từ Kalman filter nội bộ | ✅ done + test |
| `src/features.py` | `extract_plate`, `extract_face_embedding`, `set_height_calibration(camera_id, pixels_per_cm)`, `extract_pose_height` | OCR biển số (easyocr), embedding mặt (insightface/buffalo_l), ước lượng chiều cao (mediapipe pose) | ✅ done + test — height cần calibrate thật trước khi tin số liệu |
| `src/calibration.py` | `set_calibration(camera_id, pixel_points, world_points)`, `pixel_to_world`, `world_to_pixel` | Homography pixel ↔ world theo mặt phẳng đường (trong 1 camera) | ✅ done + test |
| `src/camera_registry.py` | `register_camera(camera_id, lat, lng, facing_deg, fov_deg)`, `nearby_cameras(camera_id, radius_m, travel_bearing_deg=None)`, `local_to_latlng(camera_id, world_x, world_y)` | Vị trí GIS thật + góc nhìn từng camera, tìm camera nào gần nhau (haversine + bearing), quy đổi world_pos cục bộ -> lat/lng thật | ✅ done + test |
| `src/reid.py` | `match_person`, `register_person` | Ghép danh tính người xuyên camera (cosine similarity, lưu RAM) | ✅ done + test |
| `src/storage.py` | `save_track`, `save_event`, `find_person_sightings(person_id, camera_ids, since_timestamp)`, `find_person_track_history(person_id)` | Ghi DB (sqlite, tự vá schema thiếu cột qua `_ensure_column`) + truy vấn person_id theo camera hoặc toàn bộ lịch sử | ✅ done + test |
| `src/cross_camera.py` | `resolve_global_identity(track, frame)` | Ghép person track với global person_id xuyên camera (dùng features+reid+calibration), gán `track.embedding`/`person_id`/`world_pos`/`travel_bearing_deg` (ưu tiên `tracking.predicted_velocity` từ Kalman filter, fallback lịch sử 2 điểm world_pos khi Kalman chưa có) | ✅ done + test |
| `src/person_search.py` | `search_departed_person(track, radius_m=500.0)` | Khi 1 person rời camera: tìm camera GIS gần đó theo khoảng cách + `track.travel_bearing_deg` (camera_registry) rồi tra sighting cùng person_id (storage) | ✅ done + test |
| `src/main.py` | `run_camera(camera_id, source)` | Vòng lặp 1 camera: detect→track→ghép person_id→save track→(nếu tai nạn) extract feature+save event→(nếu person rời khung hình) tìm ở camera gần đó | ✅ done + test |
| `src/storage.py` (bổ sung) | `save_camera`, `list_cameras` | Persist vị trí GIS + góc nhìn camera xuống DB (bảng `cameras`) | ✅ done + test |
| `src/api.py` | FastAPI app: `GET/POST /api/cameras`, `GET /api/tracks`, `GET /api/events`, `GET /api/persons/{id}/sightings`, `WS /ws/events`, `POST /webrtc/offer` | Đọc/ghi DB, hydrate `camera_registry` từ DB lúc khởi động app, đẩy accident event mới qua WebSocket (poll 1s), signaling WebRTC | ✅ done + test |
| `src/webrtc_stream.py` | `CameraTrack` (aiortc `VideoStreamTrack`), `build_answer(camera_id, source, offer_sdp, offer_type)` | Stream video qua WebRTC, chạy detect+track+ghép person_id mỗi frame, đẩy bbox/person_id qua DataChannel, lặp video khi hết (dùng `ingest.reset_camera`) | ✅ done + test (aiortc client thật trong test, không mock) |
| `dashboard/` | React (Vite) + Leaflet: `TrackingView.jsx` (`CRS.Simple` + WebSocket alert), `CameraConfigView.jsx` (OSM thật, click thêm/kéo camera, input hướng nhìn+FOV, vẽ cone), `LiveView.jsx` (WebRTC video + canvas overlay, click chọn người → theo dõi person_id, nút tìm ở camera khác) | Dashboard 3 tab: track/cảnh báo, cấu hình camera GIS, xem live + chọn người theo dõi | ✅ done, verify bằng browser thật (click chọn người hoạt động đúng sau khi sửa 2 bug — xem report.md) |
| `scripts/tune_accident_thresholds.py` | `tune(video_path, camera_id, output_csv)` | Chạy pipeline trên video thật, ghi CSV IOU/tốc độ thô để chọn threshold `detect_accident` dựa trên số liệu, không đoán | ✅ done + test (mock) — chưa chạy trên video thật vì chưa có |
| `scripts/draw_person_path.py` | `build_path_points(person_id)`, `render_html(person_id, points)` | Module độc lập (không cần dashboard/FastAPI): đọc lịch sử track 1 person_id, quy đổi sang lat/lng thật, sinh file HTML standalone (Leaflet+OSM qua CDN) vẽ lộ trình + mũi tên hướng đi hiện tại | ✅ done + test, verify bằng browser thật (tọa độ Hà Nội thật) |

Luồng dữ liệu: `ingest → detection → tracking → features (+ calibration) → reid → storage`, `main.py` chạy vòng lặp này cho 1 camera; `cross_camera.py` dùng khi có ≥2 camera cần ghép danh tính; `src/api.py` + `dashboard/` đọc dữ liệu đã lưu để hiển thị.
Chi tiết trạng thái/giới hạn từng phần: xem `report.md`.

### Quy trình code bắt buộc (mọi task, trừ việc quá nhỏ)
1. Nghĩ trước: xác định task đụng vào hàm nào trong bảng trên, có tái sử dụng được không — không viết lại logic đã có sẵn.
2. Code ngắn nhất giải quyết đúng việc — không thêm nhánh/tham số không ai yêu cầu.
3. Code xong → viết test verify đúng logic đó (test ngắn, không dựng framework nếu không cần).
4. Test pass rồi mới coi là xong / mới tạo thêm file khác phụ thuộc vào nó.
5. Không lan man ngoài phạm vi hàm đang implement.
