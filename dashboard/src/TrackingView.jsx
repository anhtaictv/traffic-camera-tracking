import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { API_BASE } from './api'
import './App.css'

function TrackingView() {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const markersLayer = useRef(null)
  const [events, setEvents] = useState([])

  useEffect(() => {
    // ponytail: world_x/world_y không phải lat/lng thật -> dùng CRS.Simple (mặt
    // phẳng, không có phép chiếu địa lý), đúng vì tọa độ đến từ homography camera.
    mapInstance.current = L.map(mapRef.current, { crs: L.CRS.Simple, minZoom: -5 }).setView([0, 0], 2)
    markersLayer.current = L.layerGroup().addTo(mapInstance.current)

    fetch(`${API_BASE}/api/tracks`)
      .then((res) => res.json())
      .then((tracks) => {
        // clearLayers trước khi vẽ: tránh cộng dồn marker khi effect chạy 2 lần
        // (React StrictMode ở dev) hoặc khi fetch cũ resolve sau khi đã remount.
        markersLayer.current.clearLayers()
        tracks.forEach((t) => {
          L.marker([t.world_y, t.world_x])
            .addTo(markersLayer.current)
            .bindPopup(`Track ${t.track_id} (${t.camera_id})`)
        })
      })

    fetch(`${API_BASE}/api/events`)
      .then((res) => res.json())
      .then(setEvents)

    return () => mapInstance.current.remove()
  }, [])

  useEffect(() => {
    const ws = new WebSocket(`${API_BASE.replace('http', 'ws')}/ws/events`)
    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data)
      setEvents((prev) => [event, ...prev])
    }
    return () => ws.close()
  }, [])

  return (
    <div className="app">
      <div ref={mapRef} className="map" />
      <aside className="alerts">
        <h2>Accident alerts</h2>
        <ul>
          {events.map((e) => (
            <li key={e.id}>
              <strong>{e.camera_id}</strong> — {e.vehicle_plate ?? 'chưa đọc được biển số'}
              <br />
              {new Date(e.timestamp * 1000).toLocaleTimeString()}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}

export default TrackingView
