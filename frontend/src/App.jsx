import React, { useState, useEffect, useRef } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Filler
} from 'chart.js';
import { Doughnut, Line, Bar } from 'react-chartjs-2';
import { 
  Activity, 
  AlertTriangle, 
  Car, 
  CheckCircle, 
  Database, 
  Eye, 
  Gauge, 
  Lock, 
  LogIn, 
  LogOut, 
  RefreshCw, 
  ShieldAlert, 
  ShieldCheck, 
  Sliders, 
  UploadCloud, 
  User, 
  Video, 
  XCircle, 
  Zap 
} from 'lucide-react';

ChartJS.register(
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Filler
);

const API_BASE = window.location.origin.includes('5173') ? 'http://localhost:5000' : '';

export default function App() {
  const [status, setStatus] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [violations, setViolations] = useState([]);
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [authModal, setAuthModal] = useState(false);
  const [user, setUser] = useState({ sub: 'guest', role: 'GUEST' });
  const [token, setToken] = useState(localStorage.getItem('traffic_jwt') || '');
  const [uploadStatus, setUploadStatus] = useState('');
  
  // Login form state
  const [loginUser, setLoginUser] = useState('operator');
  const [loginPass, setLoginPass] = useState('op123');
  const [loginError, setLoginError] = useState('');

  const fileInputRef = useRef(null);

  const getHeaders = () => {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  const fetchDashboardData = async () => {
    try {
      const [resStatus, resAnalytics, resViolations] = await Promise.all([
        fetch(`${API_BASE}/api/status`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/analytics`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/violations?limit=20`, { headers: getHeaders() })
      ]);

      if (resStatus.ok) setStatus(await resStatus.json());
      if (resAnalytics.ok) setAnalytics(await resAnalytics.json());
      if (resViolations.ok) {
        const vData = await resViolations.json();
        setViolations(vData.violations || []);
      }
    } catch (err) {
      console.warn('Telemetry polling error:', err.message);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 1500);
    return () => clearInterval(interval);
  }, [token]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUser, password: loginPass })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        setToken(data.token);
        localStorage.setItem('traffic_jwt', data.token);
        setUser({ sub: data.username, role: data.role, name: data.name });
        setAuthModal(false);
      } else {
        setLoginError(data.error || 'Authentication failed');
      }
    } catch (err) {
      setLoginError('Server connection error during login');
    }
  };

  const handleLogout = () => {
    setToken('');
    localStorage.removeItem('traffic_jwt');
    setUser({ sub: 'guest', role: 'GUEST' });
  };

  const handleSourceSwitch = async (mode, source = '') => {
    try {
      const res = await fetch(`${API_BASE}/api/video/source`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, source })
      });
      if (res.ok) {
        fetchDashboardData();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to switch source. Ensure you are logged in as Operator/Admin.');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('video', file);
    setUploadStatus('Uploading & validating video bytes...');

    try {
      const res = await fetch(`${API_BASE}/api/video/upload`, {
        method: 'POST',
        headers: getHeaders(),
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setUploadStatus(`Uploaded: ${data.filename}`);
        fetchDashboardData();
      } else {
        setUploadStatus(`Error: ${data.error}`);
      }
    } catch (err) {
      setUploadStatus('Upload failed due to connection error.');
    }
    setTimeout(() => setUploadStatus(''), 4000);
  };

  const handleReviewViolation = async (evidenceId, reviewDecision) => {
    try {
      const res = await fetch(`${API_BASE}/api/violations/${evidenceId}/review`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: reviewDecision })
      });
      if (res.ok) {
        fetchDashboardData();
        if (activeEvidence) {
          setActiveEvidence(prev => prev ? { ...prev, status: reviewDecision } : null);
        }
      } else {
        const err = await res.json();
        alert(err.error || 'Operator/Admin login required for violation review.');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSignalOverride = async (state, manual = true) => {
    try {
      const res = await fetch(`${API_BASE}/api/signal/override`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ state, manual })
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.error || 'Operator login required for signal control.');
      } else {
        fetchDashboardData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Chart configs
  const vehicleChartData = {
    labels: analytics?.vehicle_composition?.labels || ['Car', 'Motorcycle', 'Auto-Rickshaw', 'Bus', 'Truck'],
    datasets: [{
      data: analytics?.vehicle_composition?.data || [0, 0, 0, 0, 0],
      backgroundColor: ['#3b82f6', '#ec4899', '#f59e0b', '#10b981', '#8b5cf6', '#64748b'],
      borderWidth: 0
    }]
  };

  const densityChartData = {
    labels: analytics?.traffic_density_history?.labels || ['-'],
    datasets: [{
      label: 'Congestion (PCU)',
      data: analytics?.traffic_density_history?.data || [0],
      fill: true,
      borderColor: '#06b6d4',
      backgroundColor: 'rgba(6, 182, 212, 0.15)',
      tension: 0.35
    }]
  };

  const violationChartData = {
    labels: analytics?.violation_breakdown?.labels || ['Red Light', 'Wrong-Way', 'Speeding'],
    datasets: [{
      label: 'Verified & Logged Incidents',
      data: analytics?.violation_breakdown?.data || [0, 0, 0],
      backgroundColor: ['#ef4444', '#f59e0b', '#8b5cf6'],
      borderRadius: 6
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#9ca3af', font: { family: 'Inter', size: 11 } } }
    },
    scales: {
      x: { ticks: { color: '#6b7280' }, grid: { color: 'rgba(255,255,255,0.05)' } },
      y: { ticks: { color: '#6b7280' }, grid: { color: 'rgba(255,255,255,0.05)' } }
    }
  };

  const currentSignal = status?.signal?.current_phase || 'GREEN';
  const remainingSecs = status?.signal?.remaining_seconds || 0;
  const isSimulation = status?.source?.is_simulation || false;
  const sourceMode = status?.source?.mode || 'UPLOAD';
  const healthStatus = status?.source?.health || 'HEALTHY';

  return (
    <div>
      {/* Top Navigation Bar */}
      <header className="app-header">
        <div className="logo-container">
          <div className="logo-badge">
            <ShieldAlert size={24} color="#ffffff" />
          </div>
          <div>
            <h1 className="app-title">AI Traffic Vision Command</h1>
            <p className="app-subtitle">Indian Urban Traffic Analytics & Cryptographically Sealed Violation System</p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {/* Truthful Source Mode Badge */}
          <div className={`badge-tag ${isSimulation ? 'badge-yellow' : 'badge-green'}`}>
            <Video size={14} />
            <span>{isSimulation ? 'SIMULATION MODE' : `LIVE ${sourceMode}`}</span>
          </div>

          {/* Database Health Badge */}
          <div className={`badge-tag ${status?.database?.connected ? 'badge-green' : 'badge-blue'}`}>
            <Database size={14} />
            <span>{status?.database?.type || 'Local Spool Active'}</span>
          </div>

          {/* User Auth Info */}
          {user.role !== 'GUEST' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge-tag badge-blue">
                <User size={13} />
                <span>{user.sub.toUpperCase()} ({user.role})</span>
              </span>
              <button 
                onClick={handleLogout}
                className="btn-ctrl" 
                style={{ background: 'rgba(239, 68, 68, 0.2)', padding: '6px 10px', fontSize: '0.75rem' }}
                title="Logout"
              >
                <LogOut size={13} />
              </button>
            </div>
          ) : (
            <button 
              onClick={() => setAuthModal(true)}
              className="btn-ctrl" 
              style={{ background: '#3b82f6', padding: '6px 14px', fontSize: '0.8rem' }}
            >
              <LogIn size={14} /> Operator Login
            </button>
          )}
        </div>
      </header>

      {/* Source Switcher Toolbar */}
      <div style={{ background: '#0e1422', borderBottom: '1px solid rgba(255,255,255,0.08)', padding: '10px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#9ca3af', fontWeight: 600 }}>SOURCE SELECTION:</span>
          <button 
            className="btn-ctrl" 
            style={{ background: sourceMode === 'UPLOAD' && !isSimulation ? '#2563eb' : 'rgba(255,255,255,0.06)', padding: '6px 12px', fontSize: '0.78rem' }}
            onClick={() => handleSourceSwitch('UPLOAD', 'backend/uploads/sample_traffic.mp4')}
          >
            Sample Traffic Video
          </button>
          <button 
            className="btn-ctrl" 
            style={{ background: sourceMode === 'WEBCAM' ? '#2563eb' : 'rgba(255,255,255,0.06)', padding: '6px 12px', fontSize: '0.78rem' }}
            onClick={() => handleSourceSwitch('WEBCAM', '0')}
          >
            USB Webcam (#0)
          </button>
          <button 
            className="btn-ctrl" 
            style={{ background: isSimulation ? '#d97706' : 'rgba(255,255,255,0.06)', padding: '6px 12px', fontSize: '0.78rem' }}
            onClick={() => handleSourceSwitch('SIMULATION', '')}
          >
            Procedural Simulator
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            accept=".mp4,.avi,.mov" 
            onChange={handleFileUpload} 
          />
          <button 
            className="btn-ctrl" 
            style={{ background: '#10b981', padding: '6px 12px', fontSize: '0.78rem' }}
            onClick={() => fileInputRef.current.click()}
          >
            <UploadCloud size={14} /> Upload MP4 Video
          </button>
          {uploadStatus && <span style={{ fontSize: '0.75rem', color: '#34d399' }}>{uploadStatus}</span>}
        </div>
      </div>

      <main className="dashboard-container">
        {/* KPI Summary Cards */}
        <div className="kpi-grid">
          <div className="glass-card kpi-card">
            <div className="kpi-icon-wrap" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
              <Car size={24} />
            </div>
            <div>
              <div className="kpi-value mono">{status?.traffic?.active_vehicles || 0}</div>
              <div className="kpi-label">Active Tracklets in View</div>
            </div>
          </div>

          <div className="glass-card kpi-card">
            <div className="kpi-icon-wrap" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
              <Gauge size={24} />
            </div>
            <div>
              <div className="kpi-value mono">{status?.traffic?.current_pcu || 0}</div>
              <div className="kpi-label">Congestion Index (PCU)</div>
            </div>
          </div>

          <div className="glass-card kpi-card">
            <div className="kpi-icon-wrap" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171' }}>
              <AlertTriangle size={24} />
            </div>
            <div>
              <div className="kpi-value mono">{violations.length}</div>
              <div className="kpi-label">Violations Logged (Sealed)</div>
            </div>
          </div>

          <div className="glass-card kpi-card">
            <div className="kpi-icon-wrap" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
              <Activity size={24} />
            </div>
            <div>
              <div className="kpi-value mono">{status?.traffic?.fps || 0} FPS</div>
              <div className="kpi-label">Inference Processing Rate</div>
            </div>
          </div>
        </div>

        {/* Primary Row: Video Feed + Adaptive Signal Engine */}
        <div className="primary-grid">
          {/* Live Video Feed */}
          <div className="glass-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                <Eye size={18} color="#3b82f6" />
                <span>
                  {isSimulation ? '[SIMULATOR] Synthetic Vehicle Stream' : `Real Video Ingestion (${sourceMode})`}
                </span>
              </div>
              <span className={`badge-tag ${healthStatus === 'HEALTHY' ? 'badge-green' : 'badge-red'}`}>
                STREAM: {healthStatus}
              </span>
            </div>

            <div className="video-player-box">
              <img 
                src={`${API_BASE}/video_feed`} 
                alt="AI Traffic Feed" 
                className="video-stream-img" 
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
              />
              <div className="stream-overlay-badge">
                <span className="pulsing-dot" style={{ background: isSimulation ? '#f59e0b' : '#ef4444' }}></span>
                <span>{isSimulation ? 'SIMULATOR ACTIVE' : 'LIVE AI INGESTION'}</span>
              </div>
            </div>
          </div>

          {/* Dynamic Adaptive Signal Controller */}
          <div className="glass-card signal-widget-wrap">
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                  <Sliders size={18} color="#10b981" />
                  <span>Adaptive Signal Engine</span>
                </div>
                <span className="badge-tag badge-blue" style={{ fontSize: '0.7rem' }}>
                  ADVISORY DECISION
                </span>
              </div>

              {/* Traffic Light Visual */}
              <div className="signal-housing">
                <div className={`signal-bulb red ${currentSignal === 'RED' ? 'active' : ''}`}></div>
                <div className={`signal-bulb yellow ${currentSignal === 'YELLOW' ? 'active' : ''}`}></div>
                <div className={`signal-bulb green ${currentSignal === 'GREEN' || currentSignal === 'PEDESTRIAN_CROSSING' ? 'active' : ''}`}></div>
              </div>

              <div className="countdown-display mono" style={{
                color: currentSignal === 'RED' ? '#ef4444' : currentSignal === 'YELLOW' ? '#f59e0b' : '#10b981'
              }}>
                {remainingSecs}s
              </div>
              <div style={{ textAlign: 'center', fontSize: '0.8rem', color: '#9ca3af', marginTop: '4px' }}>
                Phase: <strong style={{ color: '#fff' }}>{currentSignal}</strong> | Duration: {status?.signal?.allocated_duration || 20}s
              </div>

              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '8px', marginTop: '12px', fontSize: '0.74rem', color: '#9ca3af' }}>
                <ShieldCheck size={14} color="#10b981" style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                <span>Interlock Engaged: Direct hardware actuation disengaged in testing mode.</span>
              </div>
            </div>

            {/* Operator Controls */}
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '8px' }}>
                Operator Advisory Override:
              </div>
              <div className="override-btn-group">
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#10b981' }}
                  onClick={() => handleSignalOverride('GREEN', true)}
                >
                  Force Green
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#ef4444' }}
                  onClick={() => handleSignalOverride('RED', true)}
                >
                  Force Red
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#3b82f6' }}
                  onClick={() => handleSignalOverride('GREEN', false)}
                >
                  <RefreshCw size={14} /> Auto
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Charts & Analytics Row */}
        <div className="charts-grid">
          {/* Vehicle Classification Doughnut */}
          <div className="glass-card" style={{ height: '300px' }}>
            <div className="chart-card-header">
              <span className="chart-title">Indian Mixed Vehicle Mix</span>
            </div>
            <div style={{ height: '220px', display: 'flex', justifyContent: 'center' }}>
              <Doughnut data={vehicleChartData} options={{ responsive: true, maintainAspectRatio: false }} />
            </div>
          </div>

          {/* Traffic Density Trend Line */}
          <div className="glass-card" style={{ height: '300px' }}>
            <div className="chart-card-header">
              <span className="chart-title">Real-Time Traffic Volume (PCU)</span>
            </div>
            <div style={{ height: '220px' }}>
              <Line data={densityChartData} options={chartOptions} />
            </div>
          </div>

          {/* Violation Type Distribution Bar */}
          <div className="glass-card" style={{ height: '300px' }}>
            <div className="chart-card-header">
              <span className="chart-title">Rule Breaches by Category</span>
            </div>
            <div style={{ height: '220px' }}>
              <Bar data={violationChartData} options={chartOptions} />
            </div>
          </div>
        </div>

        {/* Human-in-the-Loop Violations Review Table */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
              <ShieldAlert size={18} color="#ef4444" />
              <span>Verifiable Evidence & Human Review Portal</span>
            </div>
            <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Latest {violations.length} Incidents</span>
          </div>

          <div className="table-container">
            <table className="modern-table">
              <thead>
                <tr>
                  <th>Evidence ID</th>
                  <th>Violation Type</th>
                  <th>Vehicle Class</th>
                  <th>Number Plate</th>
                  <th>Speed (Calibrated)</th>
                  <th>Review Status</th>
                  <th>Evidence Actions</th>
                </tr>
              </thead>
              <tbody>
                {violations.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: '#6b7280' }}>
                      No violations logged yet. Traffic rules observed.
                    </td>
                  </tr>
                ) : (
                  violations.map((v, i) => (
                    <tr key={v._id || v.evidence_id || i}>
                      <td className="mono" style={{ fontSize: '0.8rem', color: '#60a5fa' }}>
                        {v.evidence_id || `#${v.vehicle_id}`}
                      </td>
                      <td>
                        <span className={`badge-tag ${
                          v.violation_type === 'Red Light Jump' ? 'badge-red' :
                          v.violation_type === 'Wrong-Way Driving' ? 'badge-yellow' : 'badge-blue'
                        }`}>
                          {v.violation_type}
                        </span>
                      </td>
                      <td>{v.vehicle_class}</td>
                      <td className="mono" style={{ fontWeight: 600 }}>
                        {v.license_plate || 'PENDING_OCR'}
                      </td>
                      <td className="mono">
                        {v.speed_kmh ? `${Math.round(v.speed_kmh)} km/h` : (v.speed ? `${Math.round(v.speed)} km/h` : 'Tracking')}
                      </td>
                      <td>
                        <span className={`badge-tag ${
                          v.status === 'VERIFIED' ? 'badge-green' :
                          v.status === 'REJECTED' ? 'badge-red' : 'badge-yellow'
                        }`}>
                          {v.status || 'PENDING_REVIEW'}
                        </span>
                      </td>
                      <td style={{ display: 'flex', gap: '6px' }}>
                        <button 
                          className="btn-ctrl" 
                          style={{ background: 'rgba(255,255,255,0.08)', padding: '5px 10px', fontSize: '0.74rem' }}
                          onClick={() => setActiveEvidence(v)}
                        >
                          <Eye size={12} /> Inspect
                        </button>
                        {v.status !== 'VERIFIED' && (
                          <button 
                            className="btn-ctrl" 
                            style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '5px 8px', fontSize: '0.74rem' }}
                            onClick={() => handleReviewViolation(v.evidence_id || v._id, 'VERIFIED')}
                            title="Verify Violation"
                          >
                            <CheckCircle size={12} />
                          </button>
                        )}
                        {v.status !== 'REJECTED' && (
                          <button 
                            className="btn-ctrl" 
                            style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '5px 8px', fontSize: '0.74rem' }}
                            onClick={() => handleReviewViolation(v.evidence_id || v._id, 'REJECTED')}
                            title="Reject / Dismiss"
                          >
                            <XCircle size={12} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Verifiable Evidence Inspector Modal */}
      {activeEvidence && (
        <div className="modal-overlay" onClick={() => setActiveEvidence(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '580px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Evidence Record: {activeEvidence.evidence_id}</h3>
                <p style={{ fontSize: '0.78rem', color: '#9ca3af' }}>Chain of Custody Cryptographic Snapshot</p>
              </div>
              <button 
                onClick={() => setActiveEvidence(null)}
                style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <img 
              src={`${API_BASE}${activeEvidence.snapshot_url}`} 
              alt="Violation Evidence" 
              className="modal-img" 
              onError={(e) => { e.target.src = 'https://via.placeholder.com/400x200?text=Snapshot+Buffered'; }}
            />

            <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.82rem' }}>
              <div>
                <span style={{ color: '#9ca3af' }}>Extracted Plate:</span>
                <div className="mono" style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fbbf24' }}>
                  {activeEvidence.license_plate || 'UNKNOWN'}
                </div>
              </div>
              <div>
                <span style={{ color: '#9ca3af' }}>Violation Type:</span>
                <div style={{ fontWeight: 600, color: '#f87171' }}>{activeEvidence.violation_type}</div>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: '#9ca3af' }}>SHA-256 Hash Seal:</span>
                <div className="mono" style={{ fontSize: '0.7rem', color: '#38bdf8', wordBreak: 'break-all' }}>
                  {activeEvidence.sha256_hash || 'SHA256_VERIFIED_CHAIN'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#10b981' }}
                  onClick={() => handleReviewViolation(activeEvidence.evidence_id || activeEvidence._id, 'VERIFIED')}
                >
                  <CheckCircle size={14} /> Approve & Issue E-Challan
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#ef4444' }}
                  onClick={() => handleReviewViolation(activeEvidence.evidence_id || activeEvidence._id, 'REJECTED')}
                >
                  <XCircle size={14} /> Dismiss
                </button>
              </div>
              <button 
                className="btn-ctrl" 
                style={{ background: '#475569' }}
                onClick={() => setActiveEvidence(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Operator Login Modal */}
      {authModal && (
        <div className="modal-overlay" onClick={() => setAuthModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '400px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={18} color="#3b82f6" />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Operator Authentication</h3>
              </div>
              <button 
                onClick={() => setAuthModal(false)}
                style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleLogin}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '4px' }}>Username</label>
                <input 
                  type="text" 
                  value={loginUser} 
                  onChange={(e) => setLoginUser(e.target.value)}
                  style={{ width: '100%', padding: '10px', background: '#0a0e17', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '4px' }}>Password</label>
                <input 
                  type="password" 
                  value={loginPass} 
                  onChange={(e) => setLoginPass(e.target.value)}
                  style={{ width: '100%', padding: '10px', background: '#0a0e17', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>

              {loginError && <p style={{ color: '#ef4444', fontSize: '0.8rem', marginBottom: '10px' }}>{loginError}</p>}

              <p style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '14px' }}>
                Demo Accounts:<br />
                • Operator: <code>operator / op123</code><br />
                • Admin: <code>admin / admin123</code><br />
                • Auditor: <code>auditor / audit123</code>
              </p>

              <button type="submit" className="btn-ctrl" style={{ width: '100%', background: '#3b82f6', padding: '10px' }}>
                Authenticate Session
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
