import { useState } from 'react'
import axios from 'axios'
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

// Fix for default marker icons
import L from 'leaflet'
import icon from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [formData, setFormData] = useState({
    start_lat: '39.976456',
    start_lon: '116.372623',
    end_lat: '39.944736',
    end_lon: '116.317087',
    start_time: '2025-01-15T20:00',
    end_time: '2025-01-15T20:30'
  })
  
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    
    try {
      const response = await axios.post(`${API_URL}/api/predict-trajectory`, {
        start_lat: parseFloat(formData.start_lat),
        start_lon: parseFloat(formData.start_lon),
        end_lat: parseFloat(formData.end_lat),
        end_lon: parseFloat(formData.end_lon),
        start_time: formData.start_time + ':00',
        end_time: formData.end_time + ':00',
        user_id: 0  // FIXED TO 0
      })
      
      setResult(response.data)
      setSidebarOpen(false)
    } catch (err) {
      setError(err.response?.data?.message || 'Connection error')
    } finally {
      setLoading(false)
    }
  }

  const useCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition((position) => {
        setFormData({
          ...formData,
          start_lat: position.coords.latitude.toFixed(4),
          start_lon: position.coords.longitude.toFixed(4)
        })
      })
    }
  }

  const getConfidenceColor = (level) => {
    const colors = {
      'high': '#10b981',
      'medium': '#f59e0b',
      'low': '#ef4444',
      'very_low': '#dc2626'
    }
    return colors[level] || '#6366f1'
  }

  const getMapCenter = () => {
    if (!result) return [40.7128, -74.0060]
    const lats = result.trajectory.map(p => p.lat)
    const lons = result.trajectory.map(p => p.lon)
    return [(Math.max(...lats) + Math.min(...lats)) / 2, (Math.max(...lons) + Math.min(...lons)) / 2]
  }

  const downloadJSON = () => {
    const dataStr = JSON.stringify(result, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'trajectory.json'
    link.click()
    URL.revokeObjectURL(url)
  }

  const downloadCSV = () => {
    // Create CSV header
    let csv = 'Point,Latitude,Longitude,Speed (km/h),Timestamp\n'
    
    // Add each trajectory point
    result.trajectory.forEach((point, index) => {
      csv += `${index + 1},${point.lat},${point.lon},${point.speed},${point.timestamp}\n`
    })
    
    // Add metadata at the bottom
    csv += `\nMetadata\n`
    csv += `Total Distance,${result.metadata.distance_km} km\n`
    csv += `Total Points,${result.metadata.num_points}\n`
    csv += `Confidence Score,${(result.confidence.score * 100).toFixed(2)}%\n`
    csv += `Confidence Level,${result.confidence.level}\n`
    
    const dataBlob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'trajectory.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="app-dark">
      {/* HEADER */}
      <header className="header-dark">
        <button className="menu-btn-dark" onClick={() => setSidebarOpen(!sidebarOpen)}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <h1 className="title-dark">Trajectory Predictor</h1>
        <div className="header-spacer"></div>
      </header>

      {/* SIDEBAR */}
      <div className={`sidebar-dark ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header-dark">
          <h2>New Journey</h2>
          <button className="close-btn-dark" onClick={() => setSidebarOpen(false)}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="form-dark">
          <div className="input-group-dark">
            <label>Start Location</label>
            <div className="input-row-dark">
              <input
                type="number"
                step="0.0001"
                placeholder="Latitude"
                value={formData.start_lat}
                onChange={(e) => setFormData({...formData, start_lat: e.target.value})}
                required
              />
              <input
                type="number"
                step="0.0001"
                placeholder="Longitude"
                value={formData.start_lon}
                onChange={(e) => setFormData({...formData, start_lon: e.target.value})}
                required
              />
            </div>
            <button type="button" onClick={useCurrentLocation} className="location-btn-dark">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
              </svg>
              Use Current Location
            </button>
          </div>

          <div className="input-group-dark">
            <label>End Location</label>
            <div className="input-row-dark">
              <input
                type="number"
                step="0.0001"
                placeholder="Latitude"
                value={formData.end_lat}
                onChange={(e) => setFormData({...formData, end_lat: e.target.value})}
                required
              />
              <input
                type="number"
                step="0.0001"
                placeholder="Longitude"
                value={formData.end_lon}
                onChange={(e) => setFormData({...formData, end_lon: e.target.value})}
                required
              />
            </div>
          </div>

          <div className="input-group-dark">
            <label>Start Time</label>
            <input
              type="datetime-local"
              value={formData.start_time}
              onChange={(e) => setFormData({...formData, start_time: e.target.value})}
              required
            />
          </div>

          <div className="input-group-dark">
            <label>End Time</label>
            <input
              type="datetime-local"
              value={formData.end_time}
              onChange={(e) => setFormData({...formData, end_time: e.target.value})}
              required
            />
          </div>

          <button type="submit" disabled={loading} className="submit-btn-dark">
            {loading ? (
              <>
                <div className="spinner"></div>
                Generating...
              </>
            ) : (
              'Generate Trajectory'
            )}
          </button>
        </form>

        {error && (
          <div className="error-dark">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            {error}
          </div>
        )}
      </div>

      {/* OVERLAY */}
      {sidebarOpen && <div className="overlay-dark" onClick={() => setSidebarOpen(false)}></div>}

      {/* MAP */}
      <div className="map-container-dark">
        <MapContainer 
          center={getMapCenter()} 
          zoom={result ? 13 : 12}
          style={{ height: '100%', width: '100%' }}
          zoomControl={true}
        >
          <TileLayer
  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
/>     
          {result && (
            <>
              <Marker position={[result.trajectory[0].lat, result.trajectory[0].lon]}>
                <Popup>
                  <div className="popup-dark">
                    <strong>Start</strong><br/>
                    {result.trajectory[0].lat.toFixed(4)}, {result.trajectory[0].lon.toFixed(4)}
                  </div>
                </Popup>
              </Marker>
              
              <Marker position={[
                result.trajectory[result.trajectory.length - 1].lat, 
                result.trajectory[result.trajectory.length - 1].lon
              ]}>
                <Popup>
                  <div className="popup-dark">
                    <strong>End</strong><br/>
                    {result.trajectory[result.trajectory.length - 1].lat.toFixed(4)}, 
                    {result.trajectory[result.trajectory.length - 1].lon.toFixed(4)}
                  </div>
                </Popup>
              </Marker>
              
              <Polyline 
                positions={result.trajectory.map(p => [p.lat, p.lon])}
                color={getConfidenceColor(result.confidence.level)}
                weight={4}
                opacity={1}
              />
            </>
          )}
        </MapContainer>
      </div>

      {/* FLOATING RESULTS */}
      {result && (
        <div className="results-dark">
          <div className={`glass-card confidence-${result.confidence.level}`}>
            <div className="confidence-score-dark">
              {Math.round(result.confidence.score * 100)}%
            </div>
            <div className="confidence-label-dark">
              {result.confidence.level.replace('_', ' ')} confidence
            </div>
          </div>

          {result.confidence.warning && (
            <div className="glass-card warning-dark">
              <div className="warning-icon-dark">⚠</div>
              <div className="warning-content-dark">
                <h3>{result.confidence.warning}</h3>
                <p>{result.confidence.message}</p>
                {result.confidence.reasons && (
                  <ul className="warning-reasons">
                    {result.confidence.reasons.map((reason, i) => (
                      <li key={i}>{reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          <div className="glass-card stats-dark">
            <div className="stat-dark">
              <div className="stat-value-dark">{result.metadata.distance_km}</div>
              <div className="stat-label-dark">km</div>
            </div>
            <div className="stat-divider-dark"></div>
            <div className="stat-dark">
              <div className="stat-value-dark">{result.metadata.num_points}</div>
              <div className="stat-label-dark">points</div>
            </div>
          </div>

          {/* DOWNLOAD BUTTONS */}
          <div className="glass-card download-buttons">
            <button onClick={downloadJSON} className="download-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              Download JSON
            </button>
            <button onClick={downloadCSV} className="download-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              Download CSV
            </button>
          </div>
        </div>
      )}

      {/* FAB */}
      {!sidebarOpen && (
        <button className="fab-dark" onClick={() => setSidebarOpen(true)}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </button>
      )}
    </div>
  )
}

export default App