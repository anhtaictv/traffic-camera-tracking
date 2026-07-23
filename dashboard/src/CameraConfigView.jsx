import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { API_BASE } from './api'
import './App.css'

// Sector hình quạt biểu diễn góc nhìn camera trên map.
// Quy ước bearing: 0 = Bắc, 90 = Đông (khớp với src/camera_registry.py).
function facingConePoints(lat, lng, facingDeg, fovDeg, radiusM = 80) {
  const points = [[lat, lng]]
  const steps = 12
  const startAngle = facingDeg - fovDeg / 2
  const endAngle = facingDeg + fovDeg / 2
  for (let i = 0; i <= steps; i++) {
    const angle = startAngle + ((endAngle - startAngle) * i) / steps
    const rad = (angle * Math.PI) / 180
    const dLat = (radiusM * Math.cos(rad)) / 111320
    const dLng = (radiusM * Math.sin(rad)) / (111320 * Math.cos((lat * Math.PI) / 180))
    points.push([lat + dLat, lng + dLng])
  }
  points.push([lat, lng])
  return points
}

function CameraConfigView() {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const layerRef = useRef(null)
  const [cameras, setCameras] = useState([])

  useEffect(() => {
    mapInstance.current = L.map(mapRef.current).setView([12.6683, 108.0378], 14) // Buon Ma Thuot, Dak Lak
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
    }).addTo(mapInstance.current)
    layerRef.current = L.layerGroup().addTo(mapInstance.current)

    fetch(`${API_BASE}/api/cameras`)
      .then((res) => res.json())
      .then(setCameras)

    mapInstance.current.on('click', (e) => {
      const camera_id = `cam_${Date.now()}`
      setCameras((prev) => [
        ...prev,
        { camera_id, lat: e.latlng.lat, lng: e.latlng.lng, facing_deg: 0, fov_deg: 90 },
      ])
    })

    return () => mapInstance.current.remove()
  }, [])

  useEffect(() => {
    if (!layerRef.current) return
    layerRef.current.clearLayers()
    cameras.forEach((cam, idx) => {
      const marker = L.marker([cam.lat, cam.lng], { draggable: true }).addTo(layerRef.current)
      marker.bindTooltip(cam.camera_id, { permanent: true, direction: 'top' })
      marker.on('dragend', (e) => {
        const { lat, lng } = e.target.getLatLng()
        setCameras((prev) => prev.map((c, i) => (i === idx ? { ...c, lat, lng } : c)))
      })
      L.polygon(facingConePoints(cam.lat, cam.lng, cam.facing_deg, cam.fov_deg), {
        color: '#3388ff',
        fillOpacity: 0.2,
      }).addTo(layerRef.current)
    })
  }, [cameras])

  const updateCamera = (idx, field, value) => {
    setCameras((prev) => prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c)))
  }

  const saveCamera = (cam) => {
    fetch(`${API_BASE}/api/cameras`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cam),
    })
  }

  return (
    <div className="app">
      <div ref={mapRef} className="map" />
      <aside className="alerts">
        <h2>Cameras</h2>
        <p style={{ fontSize: '0.85rem', opacity: 0.7 }}>
          Click vào map để thêm camera. Kéo marker để đổi vị trí, chỉnh số rồi bấm Lưu.
        </p>
        <ul>
          {cameras.map((cam, idx) => (
            <li key={cam.camera_id}>
              <strong>{cam.camera_id}</strong>
              <div>
                Hướng nhìn (độ, 0=Bắc):{' '}
                <input
                  type="number"
                  value={cam.facing_deg}
                  onChange={(e) => updateCamera(idx, 'facing_deg', Number(e.target.value))}
                  style={{ width: '4rem' }}
                />
              </div>
              <div>
                Góc mở FOV (độ):{' '}
                <input
                  type="number"
                  value={cam.fov_deg}
                  onChange={(e) => updateCamera(idx, 'fov_deg', Number(e.target.value))}
                  style={{ width: '4rem' }}
                />
              </div>
              <button onClick={() => saveCamera(cam)}>Lưu</button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}

export default CameraConfigView
