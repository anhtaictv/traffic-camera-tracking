import { useState } from 'react'
import TrackingView from './TrackingView'
import CameraConfigView from './CameraConfigView'
import LiveView from './LiveView'

function App() {
  const [tab, setTab] = useState('tracking')

  return (
    <div className="app-shell">
      <nav className="tabs">
        <button className={tab === 'tracking' ? 'active' : ''} onClick={() => setTab('tracking')}>
          Tracking
        </button>
        <button className={tab === 'cameras' ? 'active' : ''} onClick={() => setTab('cameras')}>
          Cameras
        </button>
        <button className={tab === 'live' ? 'active' : ''} onClick={() => setTab('live')}>
          Live
        </button>
      </nav>
      <div className="tab-content">
        {tab === 'tracking' && <TrackingView />}
        {tab === 'cameras' && <CameraConfigView />}
        {tab === 'live' && <LiveView />}
      </div>
    </div>
  )
}

export default App
