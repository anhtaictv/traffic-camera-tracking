import { useRef, useState } from 'react'
import { API_BASE } from './api'
import './App.css'

function LiveView() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const pcRef = useRef(null)
  const tracksRef = useRef([])

  const [cameraId, setCameraId] = useState('demo_cam')
  const [source, setSource] = useState('')
  const [connected, setConnected] = useState(false)
  const [selectedPersonId, setSelectedPersonId] = useState(null)
  const [sightings, setSightings] = useState([])

  const drawOverlay = () => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (!canvas || !video || !video.videoWidth) return
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
    }
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    for (const t of tracksRef.current) {
      const [x, y, w, h] = t.bbox
      const isSelected = selectedPersonId != null && t.person_id === selectedPersonId
      ctx.strokeStyle = isSelected ? '#ff3333' : t.class_id === 'person' ? '#33ff33' : '#3388ff'
      ctx.lineWidth = isSelected ? 4 : 2
      ctx.strokeRect(x, y, w, h)
      ctx.fillStyle = ctx.strokeStyle
      ctx.font = '14px sans-serif'
      ctx.fillText(`#${t.track_id}${t.person_id != null ? ' p' + t.person_id : ''}`, x, y - 4)
    }
  }

  const handleCanvasClick = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    const x = (e.clientX - rect.left) * scaleX
    const y = (e.clientY - rect.top) * scaleY

    // nhiều box có thể chồng nhau (vd. người đứng trước xe/nền lớn) -> lấy box nhỏ
    // nhất trong các box khớp thay vì box đầu tiên, để ưu tiên đối tượng cụ thể hơn.
    const matches = tracksRef.current.filter(
      (t) => x >= t.bbox[0] && x <= t.bbox[0] + t.bbox[2] && y >= t.bbox[1] && y <= t.bbox[1] + t.bbox[3]
    )
    const hit = matches.length
      ? matches.reduce((smallest, t) =>
          t.bbox[2] * t.bbox[3] < smallest.bbox[2] * smallest.bbox[3] ? t : smallest
        )
      : null
    if (hit && hit.person_id != null) {
      setSelectedPersonId(hit.person_id)
      setSightings([])
    }
  }

  const connect = async () => {
    const pc = new RTCPeerConnection()
    pcRef.current = pc

    pc.addTransceiver('video', { direction: 'recvonly' })
    const channel = pc.createDataChannel('tracks')
    channel.onmessage = (event) => {
      tracksRef.current = JSON.parse(event.data)
      drawOverlay()
    }

    pc.ontrack = (event) => {
      videoRef.current.srcObject = event.streams[0]
    }

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    const resp = await fetch(`${API_BASE}/webrtc/offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        camera_id: cameraId,
        source,
        sdp: pc.localDescription.sdp,
        type: pc.localDescription.type,
      }),
    })
    const answer = await resp.json()
    await pc.setRemoteDescription(answer)
    setConnected(true)
  }

  const disconnect = () => {
    pcRef.current?.close()
    pcRef.current = null
    setConnected(false)
    setSelectedPersonId(null)
    tracksRef.current = []
  }

  const findElsewhere = async () => {
    if (selectedPersonId == null) return
    const resp = await fetch(
      `${API_BASE}/api/persons/${selectedPersonId}/sightings?camera_id=${encodeURIComponent(cameraId)}`
    )
    setSightings(await resp.json())
  }

  return (
    <div className="app">
      <div className="live-main">
        <div className="live-controls">
          <input placeholder="camera_id" value={cameraId} onChange={(e) => setCameraId(e.target.value)} />
          <input
            placeholder="đường dẫn video demo (vd. C:\\video.mp4)"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            style={{ width: '20rem' }}
          />
          {connected ? (
            <button onClick={disconnect}>Ngắt kết nối</button>
          ) : (
            <button onClick={connect}>Kết nối</button>
          )}
        </div>
        <div className="live-video-wrap">
          <video ref={videoRef} autoPlay playsInline onPlaying={drawOverlay} />
          <canvas ref={canvasRef} onClick={handleCanvasClick} />
        </div>
      </div>
      <aside className="alerts">
        <h2>Theo dõi</h2>
        {selectedPersonId == null ? (
          <p style={{ fontSize: '0.85rem', opacity: 0.7 }}>Click vào 1 người trên video để chọn theo dõi.</p>
        ) : (
          <>
            <p>
              Đang theo dõi: <strong>person {selectedPersonId}</strong>
            </p>
            <button onClick={findElsewhere}>Tìm ở camera khác</button>
            <ul>
              {sightings.map((s, i) => (
                <li key={i}>
                  {s.camera_id} — {new Date(s.timestamp * 1000).toLocaleTimeString()}
                </li>
              ))}
            </ul>
          </>
        )}
      </aside>
    </div>
  )
}

export default LiveView
