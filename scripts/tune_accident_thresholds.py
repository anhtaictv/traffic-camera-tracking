import argparse
import csv
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":  # console Windows mặc định cp1252, không in được tiếng Việt
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ingest, detection, tracking


def tune(video_path: str, camera_id: str, output_csv: str, max_frames: int | None = None) -> int:
    """Chạy detect+track trên 1 video thật, ghi CSV IOU va chạm + tốc độ thô (chưa
    áp threshold) từng frame để chọn ngưỡng detect_accident dựa trên dữ liệu thật.
    max_frames giới hạn số frame xử lý (video dài/4K rất chậm trên CPU, không set thì
    chạy hết video). Trả về số frame đã xử lý."""
    ingest.register_camera_source(camera_id, video_path)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["frame", "kind", "track_a", "track_b", "iou", "prev_speed", "cur_speed", "decel_ratio"]
        )

        frame_idx = 0
        while max_frames is None or frame_idx < max_frames:
            frame = ingest.read_frame(camera_id)
            if frame is None:
                break

            tracks = tracking.update_tracks(camera_id, detection.detect_objects(frame))
            metrics = detection.accident_metrics(tracks)

            for track_a, track_b, iou in metrics["collisions"]:
                writer.writerow([frame_idx, "collision", track_a, track_b, iou, "", "", ""])

            for track_id, speeds in metrics["speeds"].items():
                if speeds is None:
                    continue
                prev_speed, cur_speed = speeds
                ratio = cur_speed / prev_speed if prev_speed > 0 else ""
                writer.writerow([frame_idx, "speed", track_id, "", "", prev_speed, cur_speed, ratio])

            frame_idx += 1

    print(f"Đã ghi {frame_idx} frame vào {output_csv}")
    print(
        f"Threshold hiện tại: COLLISION_IOU={detection._COLLISION_IOU_THRESHOLD}, "
        f"MIN_MOVING_SPEED={detection._MIN_MOVING_SPEED}, DECELERATION_RATIO={detection._DECELERATION_RATIO}"
    )
    print("Mở CSV, lọc dòng quanh thời điểm tai nạn thật (biết trước) để chọn ngưỡng phù hợp,")
    print("rồi sửa 3 hằng số đó trong src/detection.py.")
    return frame_idx


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ghi IOU va chạm + tốc độ thô ra CSV để tune detect_accident trên video thật"
    )
    parser.add_argument("video_path", help="Đường dẫn video tai nạn thật (hoặc RTSP URL)")
    parser.add_argument("--camera-id", default="tune_cam")
    parser.add_argument("--output", default="tune_output.csv")
    parser.add_argument("--max-frames", type=int, default=None, help="Giới hạn số frame xử lý")
    args = parser.parse_args()
    tune(args.video_path, args.camera_id, args.output, max_frames=args.max_frames)
