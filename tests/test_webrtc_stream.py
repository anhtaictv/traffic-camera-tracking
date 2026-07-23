import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription
from ultralytics.utils import ASSETS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.webrtc_stream import build_answer, CameraTrack
from src.models import Frame, Track


def _make_test_video(num_frames: int) -> str:
    path = str(Path(tempfile.mkdtemp()) / "test.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
    for _ in range(num_frames):
        writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
    writer.release()
    return path


def _make_bus_video(num_frames: int) -> str:
    img = cv2.imread(str(Path(ASSETS) / "bus.jpg"))
    h, w = img.shape[:2]
    path = str(Path(tempfile.mkdtemp()) / "bus.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
    for _ in range(num_frames):
        writer.write(img)
    writer.release()
    return path


async def _run_negotiation_and_receive_frame(video_path: str, camera_id: str, timeout: float = 15):
    client_pc = RTCPeerConnection()
    client_pc.addTransceiver("video", direction="recvonly")
    channel = client_pc.createDataChannel("tracks")

    received_frame = asyncio.get_event_loop().create_future()
    received_metadata = asyncio.get_event_loop().create_future()

    @client_pc.on("track")
    def on_track(track):
        async def consume():
            frame = await track.recv()
            if not received_frame.done():
                received_frame.set_result(frame)

        asyncio.ensure_future(consume())

    @channel.on("message")
    def on_message(message):
        if not received_metadata.done():
            received_metadata.set_result(message)

    offer = await client_pc.createOffer()
    await client_pc.setLocalDescription(offer)

    answer_sdp, answer_type = await build_answer(
        camera_id, video_path, client_pc.localDescription.sdp, client_pc.localDescription.type
    )
    await client_pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type=answer_type))

    frame = await asyncio.wait_for(received_frame, timeout=timeout)
    metadata = await asyncio.wait_for(received_metadata, timeout=timeout)

    await client_pc.close()
    return frame, metadata


def test_webrtc_offer_answer_streams_video_and_metadata():
    video_path = _make_test_video(20)
    frame, metadata = asyncio.run(_run_negotiation_and_receive_frame(video_path, "webrtc_test_cam"))

    assert frame.width == 64 and frame.height == 64
    assert metadata == "[]"  # video toàn màu đen -> YOLO không detect gì, list track rỗng


def test_webrtc_stream_saves_tracks_to_storage():
    # ponytail: detect_objects (YOLO) + resolve_global_identity (InsightFace) chạy
    # CPU-only mỗi frame -> chậm hơn nhiều so với 30fps thật, timeout dài hơn cho test.
    video_path = _make_bus_video(5)

    with patch("src.webrtc_stream.storage.save_track") as mock_save_track:
        frame, metadata = asyncio.run(
            _run_negotiation_and_receive_frame(video_path, "webrtc_bus_cam", timeout=60)
        )

    tracks = json.loads(metadata)
    assert len(tracks) > 0  # ảnh bus.jpg có người/xe -> YOLO detect được
    # video track vẫn tiếp tục sinh frame sau khi nhận được message đầu tiên (trước khi
    # pc.close() dừng hẳn) -> call_count là bội số của len(tracks), không nhất thiết bằng
    assert mock_save_track.call_count >= len(tracks)
    assert mock_save_track.call_count % len(tracks) == 0


def test_camera_track_skips_detect_using_frame_interval():
    """detect_objects chỉ chạy thật mỗi _DETECT_INTERVAL frame (chia sẻ logic với
    main.py qua _extrapolate_tracks) -> tránh giật hình do detect không kịp nhịp
    phát ~30fps cố định của aiortc."""
    frame = Frame(camera_id="cam_track_skip", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    track = Track(track_id=1, camera_id="cam_track_skip", bbox=(50.0, 50.0, 10, 10), class_id="car")

    with (
        patch("src.webrtc_stream.ingest.register_camera_source"),
        patch("src.webrtc_stream.ingest.read_frame", return_value=frame),
        patch("src.webrtc_stream.detection.detect_objects", return_value=[]) as mock_detect,
        patch("src.webrtc_stream.tracking.update_tracks", return_value=[track]) as mock_update,
        patch("src.webrtc_stream.tracking.predicted_velocity", return_value=(0.0, 0.0)),
        patch("src.webrtc_stream.storage.save_track"),
    ):
        camera_track = CameraTrack("cam_track_skip", "dummy_source")
        camera_track._process_frame()
        camera_track._process_frame()
        camera_track._process_frame()

    assert mock_detect.call_count == 2  # frame_count 0 va 2 la frame detect that
    assert mock_update.call_count == 2


if __name__ == "__main__":
    test_webrtc_offer_answer_streams_video_and_metadata()
    test_webrtc_stream_saves_tracks_to_storage()
    test_camera_track_skips_detect_using_frame_interval()
    print("OK")
