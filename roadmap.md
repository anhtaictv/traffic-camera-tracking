# Roadmap: Hệ thống phát hiện tai nạn & truy vết đối tượng đa camera

Nguồn: `noidung.txt`. Sắp xếp lại theo **thứ tự phụ thuộc thực tế** (không theo thứ tự xuất hiện trong file), vì file gốc mô tả calibration/sync ở cuối nhưng đó là nền tảng bắt buộc phải có trước khi cross-camera tracking chạy đúng.

---

## Phase 0 — Hạ tầng & dữ liệu nền (1-2 tuần)
Không có phase này thì mọi phase sau đều không có gì để chạy trên.
- Chọn nguồn camera thật (RTSP list, số lượng, độ phân giải, FPS).
- Dựng pipeline ingest: FFmpeg/GStreamer → frame queue (Kafka/RabbitMQ hoặc đơn giản là Redis Stream nếu quy mô nhỏ).
- Bảng DB tối thiểu (Postgres + PostGIS): `cameras`, `tracks`, `suspect_tracks` — dùng đúng schema mẫu trong file, không cần thêm bảng chưa dùng tới.
- **Quyết định cần chốt trước:** self-host toàn bộ (build) hay dùng giải pháp thương mại (Hikvision/Dahua/Verkada) cho một phần? File đã liệt kê bảng so sánh giá — nên chốt sớm vì ảnh hưởng toàn bộ scope phía sau.

## Phase 1 — Detection + tracking trên MỘT camera (2-3 tuần)
Chạy được trước khi nghĩ tới đa camera.
- Object detection: YOLOv8/YOLOv10 (Ultralytics) cho xe + người.
- Accident detection: rule đơn giản trước (va chạm bbox + giảm tốc đột ngột), action recognition (SlowFast/TSN) là nâng cấp sau, không phải điều kiện tiên quyết.
- Single-camera tracking: DeepSORT hoặc ByteTrack (ByteTrack nhẹ hơn, khuyến nghị bắt đầu ở đây).
- **Milestone kiểm chứng:** một camera, video test có va chạm giả lập, hệ thống tự trigger alert + track đúng 1 đối tượng hết clip.

## Phase 2 — Trích xuất đặc điểm (song song, 2-3 tuần)
Độc lập với nhau, có thể làm song song sau khi Phase 1 xong:
- **Biển số:** EasyOCR/PaddleOCR — độ chính xác cao nhất trong toàn bộ danh sách (~90%+ thực tế), làm trước vì ROI thực dụng nhất.
- **Khuôn mặt:** InsightFace/ArcFace — chỉ khả thi khi camera đủ gần/độ phân giải đủ; cần test thực tế trước khi cam kết %.
- **Dáng người/chiều cao:** MediaPipe Pose — dùng đúng code mẫu `HumanAnalyzer` trong file làm điểm khởi đầu, nhưng **công thức `torso*1.5 + leg*1.2` là hệ số tự chế, không có căn cứ đo lường thật** — cần calibrate bằng người có chiều cao biết trước đứng ở vài khoảng cách cố định trước khi tin số liệu.
- **Loại/màu/hãng xe:** vehicle classification model — độ ưu tiên thấp nhất trong Phase 2, hoãn nếu thời gian gấp.

⚠️ **Rung chuông pháp lý trước khi build tiếp:** module này thu thập đặc điểm sinh trắc học công khai (khuôn mặt, dáng người, chiều cao) của người đi đường. Trước khi lưu trữ lâu dài, cần xác nhận cơ sở pháp lý (biển báo giám sát, thời hạn lưu trữ, ai được truy cập) — đây không phải việc kỹ thuật nhưng chặn được rủi ro lớn nếu bỏ qua.

## Phase 3 — Calibration & time sync (2-4 tuần)
**Bắt buộc phải xong trước Phase 4**, vì cross-camera tracking không có ý nghĩa nếu tọa độ và mốc thời gian giữa các camera không khớp.
- Calibration: OpenCV `calibrateCamera` + chessboard — đủ dùng, không cần Kalibr/PyTorch3D (over-kill cho hệ thống giao thông cố định, không phải robot/AR).
- Homography giữa các cặp camera có overlap — dùng cho vùng có chung field-of-view.
- Time sync: **NTP là đủ** cho bài toán này (sai số chục ms chấp nhận được khi track người/xe di chuyển). PTP/hardware trigger (±1μs) là over-engineering trừ khi có yêu cầu tốc độ cao bất thường — file liệt kê 5 phương án nhưng chỉ cần 1.
- **Milestone kiểm chứng:** reprojection error < 0.5 pixel, và 2 camera adjacent cùng nhìn thấy 1 người tại cùng timestamp lệch < 50ms.

## Phase 4 — Cross-camera Re-ID tracking (3-4 tuần)
Chỉ bắt đầu sau khi Phase 1+3 chạy ổn.
- ReID model: dùng model pretrained có thật (vd. `torchreid` — package thật trên PyPI), **không phải `pytorch-reid-torch` hay `reid.torchmodels.resnet50` như trong file — hai tên này không tồn tại, code mẫu trong `noidung.txt` không chạy được nguyên trạng.**
- `PersonTrackManager` + cosine similarity matching — logic trong file dùng được, giữ nguyên.
- Global coordinate mapping dùng `CoordinateTransformer` từ Phase 3.
- **Milestone kiểm chứng:** 1 người đi bộ qua 2 camera có overlap, hệ thống gán cùng 1 global ID.

## Phase 5 — Dashboard & alerting (2 tuần)
- Web dashboard (React/Vue) + map (Leaflet) — chỉ cần đọc dữ liệu từ Postgres/PostGIS đã có ở Phase 0, không cần thiết kế lại data model.
- Real-time alert qua WebSocket khi có `accident_alert` mới.

## Phase 6 — Hardening / production (liên tục sau khi có bản chạy được)
- Multi-processing / batch inference để tăng throughput (file có gợi ý `Pool`, dùng khi đã đo được bottleneck thật, không làm trước).
- Monitoring drift của calibration & sync theo thời gian.
- Video archive retention policy (30-90 ngày theo file) — gắn với quyết định pháp lý ở Phase 2.

---

## Tổng quan phụ thuộc

```
Phase 0 (hạ tầng)
   └─▶ Phase 1 (single-camera detect+track)
           ├─▶ Phase 2 (đặc điểm: biển số/mặt/dáng người)  [song song]
           └─▶ Phase 3 (calibration + time sync)
                    └─▶ Phase 4 (cross-camera Re-ID)
                             └─▶ Phase 5 (dashboard)
                                      └─▶ Phase 6 (hardening)
```

## Việc cần bạn quyết định trước khi code Phase 1
1. Build tự làm toàn bộ hay mua giải pháp thương mại cho một phần (camera AI có sẵn)?
2. Có camera/RTSP thật để test không, hay chỉ có video mẫu?
3. Yêu cầu pháp lý về lưu trữ khuôn mặt/dáng người đã được xác nhận chưa?

→ skipped: code thật cho từng phase (chỉ làm roadmap theo yêu cầu), bắt đầu code khi bạn chọn 1 phase ở Phase 1 hoặc Phase 2.
