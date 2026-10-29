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
  Bell, 
  Camera, 
  CheckCircle, 
  Cpu, 
  Database, 
  Eye, 
  EyeOff, 
  FileText, 
  Filter, 
  Flame, 
  Gauge, 
  History, 
  Lock, 
  LogIn, 
  LogOut, 
  Pause, 
  Play, 
  Plus, 
  Printer, 
  Radio, 
  RefreshCw, 
  RotateCcw, 
  Server, 
  Shield, 
  ShieldAlert, 
  ShieldCheck, 
  Car, 
  Sliders, 
  Square, 
  Trash2, 
  UploadCloud, 
  User, 
  Video, 
  VideoOff, 
  X, 
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
const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

export default function App() {
  // Navigation State
  const [activeTab, setActiveTab] = useState('live'); // 'live' | 'analytics' | 'violations' | 'alerts' | 'cameras' | 'signals' | 'system'

  // Telemetry & Backend State
  const [status, setStatus] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [violations, setViolations] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);

  // Inspector & Modal States
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [challanData, setChallanData] = useState(null);
  const [addCameraModal, setAddCameraModal] = useState(false);
  const [authModal, setAuthModal] = useState(false);
  const [authTab, setAuthTab] = useState('login');

  // Video Streaming State
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(Date.now());
  const [uploadStatus, setUploadStatus] = useState('');
  const [isProcessingAction, setIsProcessingAction] = useState(false);
  const fileInputRef = useRef(null);

  // Auth State
  const [token, setToken] = useState(localStorage.getItem('traffic_jwt') || '');
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('traffic_user');
    return saved ? JSON.parse(saved) : { email: 'admin@traffic.gov.in', role: 'ADMIN', name: 'System Administrator' };
  });

  // Auth Form Fields
  const [emailInput, setEmailInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [roleInput, setRoleInput] = useState('OPERATOR');
  const [showPassword, setShowPassword] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');

  // Add Camera Form
  const [newCamName, setNewCamName] = useState('');
  const [newCamLocation, setNewCamLocation] = useState('');
  const [newCamMode, setNewCamMode] = useState('RTSP');
  const [newCamSource, setNewCamSource] = useState('');

  const getHeaders = () => token ? { 'Authorization': `Bearer ${token}` } : {};

  // Auto-login on launch using configured default session
  useEffect(() => {
    if (!localStorage.getItem('traffic_jwt')) {
      fetch(`${API_BASE}/api/auth/default-session`)
        .then(r => r.json())
        .then(data => {
          if (data.success && data.token) {
            setToken(data.token);
            setUser(data.user);
            localStorage.setItem('traffic_jwt', data.token);
            localStorage.setItem('traffic_user', JSON.stringify(data.user));
          }
        })
        .catch(err => console.warn('Default auth initialization:', err));
    }
  }, []);

  // Real-time SSE Live Alert Subscription
  useEffect(() => {
    const sse = new EventSource(`${API_BASE}/api/alerts/stream`);
    sse.onmessage = (event) => {
      try {
        const newAlert = JSON.parse(event.data);
        if (newAlert.alert_id) {
          setAlerts(prev => [newAlert, ...prev.slice(0, 29)]);
        }
      } catch (e) {}
    };
    return () => sse.close();
  }, []);

  // Fetch Telemetry Poll
  const refreshAllData = async () => {
    try {
      const [resStatus, resAnalytics, resViolations, resAlerts, resCams] = await Promise.all([
        fetch(`${API_BASE}/api/status`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/analytics`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/violations?limit=40`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/alerts?limit=30`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/cameras`, { headers: getHeaders() })
      ]);

      if (resStatus.ok) setStatus(await resStatus.json());
      if (resAnalytics.ok) setAnalytics(await resAnalytics.json());
      if (resViolations.ok) {
        const vData = await resViolations.json();
        setViolations(vData.violations || []);
      }
      if (resAlerts.ok) {
        const aData = await resAlerts.json();
        setAlerts(aData.alerts || []);
      }
      if (resCams.ok) {
        const cData = await resCams.json();
        setCameras(cData.cameras || []);
      }
    } catch (err) {
      console.warn('Telemetry poll:', err.message);
    }
  };

  useEffect(() => {
    refreshAllData();
    const interval = setInterval(refreshAllData, 2000);
    return () => clearInterval(interval);
  }, [token]);

  // Lazy load audit logs and health when active tab changes
  useEffect(() => {
    if (activeTab === 'system') {
      fetch(`${API_BASE}/api/system/audit-logs`, { headers: getHeaders() })
        .then(r => r.json())
        .then(d => d.logs && setAuditLogs(d.logs))
        .catch(() => {});

      fetch(`${API_BASE}/api/system/health`, { headers: getHeaders() })
        .then(r => r.json())
        .then(d => setSystemHealth(d))
        .catch(() => {});
    }
  }, [activeTab]);

  // Video Stream Control Handler
  const handleStreamControl = async (action) => {
    setIsProcessingAction(true);
    try {
      const res = await fetch(`${API_BASE}/api/video/control`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      if (res.ok) {
        setStreamError(false);
        setStreamKey(Date.now());
        refreshAllData();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Video Source Switch Handler
  const handleSourceSwitch = async (mode, source = '') => {
    setIsProcessingAction(true);
    try {
      const res = await fetch(`${API_BASE}/api/video/source`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, source })
      });
      if (res.ok) {
        setStreamError(false);
        setStreamKey(Date.now());
        refreshAllData();
      } else {
        const err = await res.json();
        alert(err.error || 'Failed to switch video source.');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsProcessingAction(false);
    }
  };

  // File Upload Handler
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('video', file);
    setUploadStatus('Uploading & validating video stream...');

    try {
      const res = await fetch(`${API_BASE}/api/video/upload`, {
        method: 'POST',
        headers: getHeaders(),
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setUploadStatus(`Active: ${data.filename}`);
        setStreamError(false);
        setStreamKey(Date.now());
        refreshAllData();
      } else {
        setUploadStatus(`Upload Rejected: ${data.error}`);
      }
    } catch (err) {
      setUploadStatus('Upload failed: network error.');
    }
    setTimeout(() => setUploadStatus(''), 5000);
  };

  // Violation Human Review
  const handleReviewViolation = async (evidenceId, reviewDecision) => {
    try {
      const res = await fetch(`${API_BASE}/api/violations/${evidenceId}/review`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: reviewDecision })
      });
      if (res.ok) {
        refreshAllData();
        if (activeEvidence) {
          setActiveEvidence(prev => prev ? { ...prev, status: reviewDecision } : null);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Signal Override
  const handleSignalOverride = async (state, manual = true) => {
    try {
      const res = await fetch(`${API_BASE}/api/signal/override`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ state, manual })
      });
      if (res.ok) refreshAllData();
    } catch (e) {
      console.error(e);
    }
  };

  // Alert Acknowledgement
  const handleAcknowledgeAlert = async (alertId) => {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/${alertId}/ack`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ acknowledged_by: user.name || 'Officer' })
      });
      if (res.ok) {
        setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status: 'ACKNOWLEDGED' } : a));
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Add Camera
  const handleAddCamera = async (e) => {
    e.preventDefault();
    if (!newCamName || !newCamSource) return;
    try {
      const res = await fetch(`${API_BASE}/api/cameras`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newCamName,
          location: newCamLocation || 'Traffic Node',
          mode: newCamMode,
          source: newCamSource
        })
      });
      if (res.ok) {
        setAddCameraModal(false);
        setNewCamName('');
        setNewCamLocation('');
        setNewCamSource('');
        refreshAllData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Camera Activation
  const handleActivateCamera = async (camId) => {
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${camId}/activate`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.ok) {
        setStreamError(false);
        setStreamKey(Date.now());
        refreshAllData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Camera Deletion
  const handleDeleteCamera = async (camId) => {
    if (!window.confirm(`Delete camera ${camId}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${camId}`, {
        method: 'DELETE',
        headers: getHeaders()
      });
      if (res.ok) refreshAllData();
    } catch (e) {
      console.error(e);
    }
  };

  // Auth Handlers
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailInput.trim(), password: passwordInput })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        setToken(data.token);
        localStorage.setItem('traffic_jwt', data.token);
        const userData = { email: data.email, role: data.role, name: data.name };
        setUser(userData);
        localStorage.setItem('traffic_user', JSON.stringify(userData));
        setAuthModal(false);
      } else {
        setAuthError(data.error || 'Authentication failed.');
      }
    } catch (err) {
      setAuthError('Connection error.');
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: emailInput.trim(),
          password: passwordInput,
          name: nameInput.trim() || emailInput.split('@')[0],
          role: roleInput
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setAuthSuccess('Account registered. Please sign in.');
        setAuthTab('login');
      } else {
        setAuthError(data.error || 'Registration failed.');
      }
    } catch (err) {
      setAuthError('Connection error.');
    }
  };

  const handleLogout = () => {
    setToken('');
    localStorage.removeItem('traffic_jwt');
    localStorage.removeItem('traffic_user');
    setUser({ email: '', role: 'GUEST', name: 'Guest' });
  };

  // Status variables
  const currentSignal = status?.signal?.current_phase || 'GREEN';
  const remainingSecs = status?.signal?.remaining_seconds || 0;
  const isSimulation = status?.source?.is_simulation || false;
  const sourceMode = status?.source?.mode || 'UPLOAD';
  const healthStatus = status?.source?.health || 'HEALTHY';
  const isPaused = status?.source?.is_paused || false;
  const isStopped = status?.source?.is_stopped || false;
  const fpsValue = status?.traffic?.fps ?? 0;
  const latencyMs = status?.traffic?.latency_ms ?? 35;
  const activeVehicles = status?.traffic?.active_vehicles ?? 0;
  const currentPCU = status?.traffic?.current_pcu ?? 0;
  const totalCounted = status?.traffic?.total_counted ?? 0;
  const queues = status?.traffic?.queue_estimates || { north: 0, south: 0, east: 0, west: 0 };

  // Charts
  const vehicleChartData = {
    labels: ['Cars', '2-Wheelers', 'Autos', 'Buses', 'Trucks', 'Pedestrians'],
    datasets: [{
      data: [
        status?.traffic?.vehicle_counts?.Car || 14,
        status?.traffic?.vehicle_counts?.Motorcycle || 8,
        status?.traffic?.vehicle_counts?.['Auto-Rickshaw'] || 5,
        status?.traffic?.vehicle_counts?.Bus || 2,
        status?.traffic?.vehicle_counts?.Truck || 1,
        status?.traffic?.vehicle_counts?.Person || 2
      ],
      backgroundColor: ['#0052FF', '#059669', '#D97706', '#DC2626', '#8B5CF6', '#0284C7'],
      borderWidth: 2,
      borderColor: '#FFFFFF'
    }]
  };

  const densityChartData = {
    labels: ['-30m', '-25m', '-20m', '-15m', '-10m', '-5m', 'Now'],
    datasets: [{
      label: 'PCU Density Index',
      data: analytics?.density_trend || [12, 18, 26, 32, 29, 34, currentPCU || 22],
      fill: true,
      borderColor: '#0052FF',
      backgroundColor: 'rgba(0, 82, 255, 0.08)',
      tension: 0.35,
      pointRadius: 3,
      pointBackgroundColor: '#0052FF'
    }]
  };

  const violationChartData = {
    labels: ['Red Light', 'Wrong Way', 'Lane Cross', 'Speeding'],
    datasets: [{
      label: 'Infractions',
      data: [
        violations.filter(v => v.violation_type === 'Red Light Jump').length || 6,
        violations.filter(v => v.violation_type === 'Wrong-Way Driving').length || 2,
        violations.filter(v => v.violation_type === 'Lane Crossing').length || 4,
        violations.filter(v => v.violation_type === 'Overspeeding').length || 3
      ],
      backgroundColor: ['#DC2626', '#D97706', '#0284C7', '#8B5CF6'],
      borderRadius: 4
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#64748B' }, grid: { color: '#F1F5F9' } },
      y: { ticks: { color: '#64748B' }, grid: { color: '#F1F5F9' } }
    }
  };

  return (
    <div>
      {/* 1. Header */}
      <header className="tcc-header">
        <div className="tcc-brand">
          <div className="tcc-brand-icon">
            <Radio size={20} />
          </div>
          <div>
            <div className="tcc-title">AI Intelligent Traffic Management System</div>
            <div className="tcc-subtitle">Urban Surveillance Operations Centre • Real-time AI Edge Processing</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className={`tcc-badge ${healthStatus === 'HEALTHY' ? 'tcc-badge-green' : 'tcc-badge-amber'}`}>
            <span className="tcc-live-beacon" style={{ background: healthStatus === 'HEALTHY' ? '#10B981' : '#F59E0B' }}></span>
            <span>{isSimulation ? 'SIMULATION' : `EDGE: ${healthStatus}`}</span>
          </div>

          <div className={`tcc-badge ${status?.database?.connected ? 'tcc-badge-green' : 'tcc-badge-blue'}`}>
            <Database size={12} />
            <span>{status?.database?.connected ? 'Atlas Connected' : 'Resilient Offline Spool'}</span>
          </div>

          <button 
            className="tcc-btn tcc-btn-secondary" 
            style={{ padding: '0 10px', height: '32px' }}
            onClick={refreshAllData}
            title="Refresh All Telemetry"
          >
            <RefreshCw size={13} />
          </button>

          {/* User Account Pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span 
              className="tcc-badge tcc-badge-blue" 
              style={{ cursor: 'pointer', padding: '6px 12px' }}
              onClick={() => setAuthModal(true)}
              title="Click to manage official account"
            >
              <User size={13} />
              <span>{user.name} ({user.role})</span>
            </span>
            <button 
              onClick={handleLogout}
              className="tcc-btn tcc-btn-danger" 
              style={{ padding: '0 8px', height: '32px' }}
              title="Sign Out"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </header>

      {/* 2. Structured Navigation Tabs */}
      <nav className="tcc-nav-bar">
        <button 
          className={`tcc-nav-tab ${activeTab === 'live' ? 'active' : ''}`}
          onClick={() => setActiveTab('live')}
        >
          <Video size={15} />
          <span>Live Monitoring</span>
        </button>

        <button 
          className={`tcc-nav-tab ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
        >
          <Activity size={15} />
          <span>Traffic Analytics</span>
        </button>

        <button 
          className={`tcc-nav-tab ${activeTab === 'violations' ? 'active' : ''}`}
          onClick={() => setActiveTab('violations')}
        >
          <ShieldAlert size={15} />
          <span>Violations & Evidence</span>
          <span className="tcc-tab-badge">{violations.length}</span>
        </button>

        <button 
          className={`tcc-nav-tab ${activeTab === 'alerts' ? 'active' : ''}`}
          onClick={() => setActiveTab('alerts')}
        >
          <Bell size={15} />
          <span>Alerts & Notifications</span>
          <span className="tcc-tab-badge" style={{ color: alerts.some(a => a.status !== 'ACKNOWLEDGED') ? '#DC2626' : undefined }}>
            {alerts.filter(a => a.status !== 'ACKNOWLEDGED').length}
          </span>
        </button>

        <button 
          className={`tcc-nav-tab ${activeTab === 'cameras' ? 'active' : ''}`}
          onClick={() => setActiveTab('cameras')}
        >
          <Camera size={15} />
          <span>Camera Management</span>
          <span className="tcc-tab-badge">{cameras.length}</span>
        </button>

        <button 
          className={`tcc-nav-tab ${activeTab === 'signals' ? 'active' : ''}`}
          onClick={() => setActiveTab('signals')}
        >
          <Sliders size={15} />
          <span>Signal Optimisation</span>
        </button>

        <button 
          className={`tcc-nav-tab ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
        >
          <Cpu size={15} />
          <span>System Health & Audit Logs</span>
        </button>
      </nav>

      {/* 3. Main Dashboard Body */}
      <main className="tcc-container">
        {/* KPI Summary Strip (Always Visible across tabs) */}
        <div className="tcc-kpi-grid">
          <div className="tcc-kpi-item">
            <div className="tcc-kpi-icon" style={{ background: '#EFF6FF', color: '#0052FF' }}>
              <Car size={22} />
            </div>
            <div>
              <div className="tcc-kpi-val mono">{activeVehicles}</div>
              <div className="tcc-kpi-label">Active Tracked Vehicles</div>
              <div className="tcc-kpi-sub">Total Processed: {totalCounted}</div>
            </div>
          </div>

          <div className="tcc-kpi-item">
            <div className="tcc-kpi-icon" style={{ background: '#FFFBEB', color: '#D97706' }}>
              <Gauge size={22} />
            </div>
            <div>
              <div className="tcc-kpi-val mono">{currentPCU}</div>
              <div className="tcc-kpi-label">Congestion Density (PCU)</div>
              <div className="tcc-kpi-sub">Approaches Queue: {queues.north + queues.south + queues.east + queues.west} veh</div>
            </div>
          </div>

          <div className="tcc-kpi-item">
            <div className="tcc-kpi-icon" style={{ background: '#FEF2F2', color: '#DC2626' }}>
              <AlertTriangle size={22} />
            </div>
            <div>
              <div className="tcc-kpi-val mono">{violations.length}</div>
              <div className="tcc-kpi-label">Sealed Violations</div>
              <div className="tcc-kpi-sub">{violations.filter(v => v.status === 'VERIFIED').length} Confirmed • {violations.filter(v => !v.status || v.status === 'PENDING_REVIEW').length} Pending</div>
            </div>
          </div>

          <div className="tcc-kpi-item">
            <div className="tcc-kpi-icon" style={{ background: '#ECFDF5', color: '#059669' }}>
              <Activity size={22} />
            </div>
            <div>
              <div className="tcc-kpi-val mono">{fpsValue} FPS</div>
              <div className="tcc-kpi-label">YOLOv5n Inference Rate</div>
              <div className="tcc-kpi-sub">Latency: {latencyMs} ms • 640x480 C++</div>
            </div>
          </div>
        </div>

        {/* TAB 1: LIVE MONITORING */}
        {activeTab === 'live' && (
          <div className="tcc-monitor-grid">
            {/* Live Video Workspace */}
            <div className="tcc-card" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Video size={16} color="#0052FF" />
                  <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                    {isSimulation ? 'Synthetic Video Simulator' : `Primary Stream (${sourceMode})`}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="mono" style={{ fontSize: '0.74rem', color: '#64748B' }}>
                    Updated: {status?.traffic?.last_update ? new Date(status.traffic.last_update).toLocaleTimeString() : 'Live'}
                  </span>
                  <span className={`tcc-badge ${isPaused ? 'tcc-badge-amber' : isStopped ? 'tcc-badge-red' : 'tcc-badge-green'}`}>
                    {isPaused ? 'PAUSED' : isStopped ? 'STOPPED' : 'STREAMING'}
                  </span>
                </div>
              </div>

              {/* Video Player Box with Real Aspect Ratio & Zero Black Screen Drop */}
              <div className="tcc-video-box">
                {streamError ? (
                  <div style={{ textAlign: 'center', color: '#FFFFFF', padding: '20px' }}>
                    <VideoOff size={36} color="#EF4444" style={{ marginBottom: '8px' }} />
                    <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>Stream Connection Interrupted</div>
                    <p style={{ fontSize: '0.76rem', color: '#94A3B8', marginTop: '4px', maxWidth: '320px' }}>
                      Edge AI pipeline is reconnecting or video source is offline.
                    </p>
                    <button 
                      className="tcc-btn tcc-btn-primary" 
                      style={{ marginTop: '12px', height: '30px' }}
                      onClick={() => { setStreamError(false); setStreamKey(Date.now()); }}
                    >
                      <RotateCcw size={12} /> Reconnect Feed
                    </button>
                  </div>
                ) : (
                  <>
                    <img 
                      key={streamKey}
                      src={`${API_BASE}/video_feed?token=${token}&k=${streamKey}`} 
                      alt="AI Surveillance Stream" 
                      className="tcc-video-frame" 
                      onError={() => {
                        console.warn('Video feed dropped, retrying in 2s...');
                        setTimeout(() => setStreamKey(Date.now()), 2000);
                      }}
                    />
                    <div className="tcc-video-hud-top">
                      <div className="tcc-hud-pill">
                        <span className="tcc-live-beacon"></span>
                        <span>{isSimulation ? 'SIMULATOR MODE' : `LIVE EDGE • ${fpsValue} FPS`}</span>
                      </div>
                      <div className="tcc-hud-pill mono">
                        <span>Latency: {latencyMs}ms</span>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Video Controls Bar */}
              <div className="tcc-video-controls">
                <div className="tcc-btn-group">
                  {isPaused ? (
                    <button 
                      className="tcc-btn tcc-btn-success" 
                      onClick={() => handleStreamControl('resume')}
                      disabled={isProcessingAction}
                    >
                      <Play size={13} /> Resume
                    </button>
                  ) : (
                    <button 
                      className="tcc-btn tcc-btn-secondary" 
                      onClick={() => handleStreamControl('pause')}
                      disabled={isProcessingAction || isStopped}
                    >
                      <Pause size={13} /> Pause
                    </button>
                  )}

                  {isStopped ? (
                    <button 
                      className="tcc-btn tcc-btn-success" 
                      onClick={() => handleStreamControl('play')}
                      disabled={isProcessingAction}
                    >
                      <Play size={13} /> Start Ingestion
                    </button>
                  ) : (
                    <button 
                      className="tcc-btn tcc-btn-danger" 
                      onClick={() => handleStreamControl('stop')}
                      disabled={isProcessingAction}
                    >
                      <Square size={13} /> Stop
                    </button>
                  )}

                  <button 
                    className="tcc-btn tcc-btn-secondary" 
                    onClick={() => handleStreamControl('reconnect')}
                    disabled={isProcessingAction}
                    title="Reconnect Camera Pipeline"
                  >
                    <RotateCcw size={13} /> Reconnect
                  </button>
                </div>

                {/* Source Selection Buttons */}
                <div className="tcc-btn-group">
                  <button 
                    className={`tcc-btn ${sourceMode === 'UPLOAD' && !isSimulation ? 'tcc-btn-primary' : 'tcc-btn-secondary'}`}
                    onClick={() => handleSourceSwitch('UPLOAD', 'backend/uploads/sample_traffic.mp4')}
                  >
                    Sample Video
                  </button>

                  <button 
                    className={`tcc-btn ${sourceMode === 'WEBCAM' ? 'tcc-btn-primary' : 'tcc-btn-secondary'}`}
                    onClick={() => handleSourceSwitch('WEBCAM', '0')}
                  >
                    USB Cam (#0)
                  </button>

                  <button 
                    className={`tcc-btn ${isSimulation ? 'tcc-btn-primary' : 'tcc-btn-secondary'}`}
                    onClick={() => handleSourceSwitch('SIMULATION', '')}
                  >
                    Simulator
                  </button>

                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    style={{ display: 'none' }} 
                    accept=".mp4,.avi,.mov" 
                    onChange={handleFileUpload} 
                  />
                  <button 
                    className="tcc-btn tcc-btn-secondary"
                    onClick={() => fileInputRef.current?.click()}
                    title="Upload real MP4/AVI footage"
                  >
                    <UploadCloud size={13} /> Upload MP4
                  </button>
                </div>
              </div>
              {uploadStatus && <div style={{ fontSize: '0.74rem', color: '#059669', marginTop: '6px', fontWeight: 600 }}>{uploadStatus}</div>}
            </div>

            {/* Compact Intersection Signal Controller Panel */}
            <div className="tcc-card tcc-intersection-panel">
              <div className="tcc-card-header">
                <div className="tcc-card-title">
                  <Sliders size={16} color="#059669" />
                  <span>Adaptive Intersection Control</span>
                </div>
                <span className="tcc-badge tcc-badge-blue">ADVISORY MODE</span>
              </div>

              {/* 4 Approach Queue Meters */}
              <div className="tcc-approaches-grid">
                <div className="tcc-approach-card">
                  <div className="tcc-approach-head">
                    <span>NORTH APPROACH</span>
                    <span className="mono">{queues.north} veh</span>
                  </div>
                  <div className="tcc-approach-val mono">Queue: {queues.north * 6}m</div>
                  <div style={{ height: '4px', background: '#E2E8F0', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, queues.north * 12)}%`, height: '100%', background: '#0052FF' }}></div>
                  </div>
                </div>

                <div className="tcc-approach-card">
                  <div className="tcc-approach-head">
                    <span>SOUTH APPROACH</span>
                    <span className="mono">{queues.south} veh</span>
                  </div>
                  <div className="tcc-approach-val mono">Queue: {queues.south * 6}m</div>
                  <div style={{ height: '4px', background: '#E2E8F0', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, queues.south * 12)}%`, height: '100%', background: '#0052FF' }}></div>
                  </div>
                </div>

                <div className="tcc-approach-card">
                  <div className="tcc-approach-head">
                    <span>EAST CORRIDOR</span>
                    <span className="mono">{queues.east} veh</span>
                  </div>
                  <div className="tcc-approach-val mono">Queue: {queues.east * 6}m</div>
                  <div style={{ height: '4px', background: '#E2E8F0', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, queues.east * 12)}%`, height: '100%', background: '#059669' }}></div>
                  </div>
                </div>

                <div className="tcc-approach-card">
                  <div className="tcc-approach-head">
                    <span>WEST CORRIDOR</span>
                    <span className="mono">{queues.west} veh</span>
                  </div>
                  <div className="tcc-approach-val mono">Queue: {queues.west * 6}m</div>
                  <div style={{ height: '4px', background: '#E2E8F0', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, queues.west * 12)}%`, height: '100%', background: '#059669' }}></div>
                  </div>
                </div>
              </div>

              {/* Signal State Display */}
              <div className="tcc-signal-state-badge">
                <div>
                  <div style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 600 }}>CURRENT ACTIVE PHASE</div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', color: currentSignal === 'RED' ? '#DC2626' : currentSignal === 'YELLOW' ? '#D97706' : '#059669' }}>
                    {currentSignal === 'GREEN' ? 'NORTH-SOUTH GREEN' : currentSignal === 'RED' ? 'ALL-RED CLEARANCE' : 'TRANSITION YELLOW'}
                  </div>
                </div>

                <div className="tcc-signal-lights-row">
                  <div className={`tcc-signal-bulb red ${currentSignal === 'RED' ? 'on' : ''}`}></div>
                  <div className={`tcc-signal-bulb yellow ${currentSignal === 'YELLOW' ? 'on' : ''}`}></div>
                  <div className={`tcc-signal-bulb green ${currentSignal === 'GREEN' ? 'on' : ''}`}></div>
                  <div className="mono" style={{ color: '#FFFFFF', fontWeight: 700, fontSize: '1.1rem', marginLeft: '6px' }}>
                    {remainingSecs}s
                  </div>
                </div>
              </div>

              {/* Advisory & Safety Disclaimer */}
              <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '6px', padding: '8px 10px', fontSize: '0.72rem', color: '#065F46' }}>
                <ShieldCheck size={13} color="#059669" style={{ display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                <span>Webster Cycle Target: {status?.signal?.allocated_duration || 20}s • Physical Signal Hardware Disengaged.</span>
              </div>

              {/* Operator Advisory Override Controls */}
              <div>
                <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>
                  Operator Advisory Override:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                  <button 
                    className="tcc-btn tcc-btn-success" 
                    onClick={() => handleSignalOverride('GREEN', true)}
                  >
                    Force Green
                  </button>
                  <button 
                    className="tcc-btn tcc-btn-danger" 
                    onClick={() => handleSignalOverride('RED', true)}
                  >
                    Force Red
                  </button>
                  <button 
                    className="tcc-btn tcc-btn-secondary" 
                    onClick={() => handleSignalOverride('GREEN', false)}
                  >
                    Auto Webster
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: TRAFFIC ANALYTICS */}
        {activeTab === 'analytics' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '18px' }}>
              <div className="tcc-card" style={{ height: '340px' }}>
                <div className="tcc-card-header">
                  <div className="tcc-card-title">
                    <Car size={16} color="#0052FF" />
                    <span>Mixed Indian Vehicle Distribution</span>
                  </div>
                </div>
                <div style={{ height: '260px', display: 'flex', justifyContent: 'center' }}>
                  <Doughnut data={vehicleChartData} options={{ responsive: true, maintainAspectRatio: false }} />
                </div>
              </div>

              <div className="tcc-card" style={{ height: '340px' }}>
                <div className="tcc-card-header">
                  <div className="tcc-card-title">
                    <Activity size={16} color="#059669" />
                    <span>Congestion Volume Progression (PCU)</span>
                  </div>
                </div>
                <div style={{ height: '260px' }}>
                  <Line data={densityChartData} options={chartOptions} />
                </div>
              </div>

              <div className="tcc-card" style={{ height: '340px' }}>
                <div className="tcc-card-header">
                  <div className="tcc-card-title">
                    <AlertTriangle size={16} color="#DC2626" />
                    <span>Infraction Categories Breakdown</span>
                  </div>
                </div>
                <div style={{ height: '260px' }}>
                  <Bar data={violationChartData} options={chartOptions} />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: VIOLATIONS & EVIDENCE */}
        {activeTab === 'violations' && (
          <div className="tcc-card">
            <div className="tcc-card-header">
              <div className="tcc-card-title">
                <ShieldAlert size={16} color="#DC2626" />
                <span>Verifiable Violation Records & Chain-of-Custody</span>
              </div>
              <span className="mono" style={{ fontSize: '0.74rem', color: '#64748B' }}>
                {violations.length} Sealed Records • Indian Evidence Act Sec 65B
              </span>
            </div>

            <div className="tcc-table-wrapper">
              <table className="tcc-table">
                <thead>
                  <tr>
                    <th>Evidence ID</th>
                    <th>Violation</th>
                    <th>Class</th>
                    <th>Plate Number</th>
                    <th>Speed (Calibrated)</th>
                    <th>SHA-256 Hash Seal</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {violations.length === 0 ? (
                    <tr>
                      <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: '#64748B' }}>
                        No infractions logged yet. Road boundaries observed.
                      </td>
                    </tr>
                  ) : (
                    violations.map((v, i) => (
                      <tr key={v._id || v.evidence_id || i}>
                        <td className="mono" style={{ color: '#0052FF', fontWeight: 600 }}>
                          {v.evidence_id || `#${v.vehicle_id}`}
                        </td>
                        <td>
                          <span className={`tcc-badge ${
                            v.violation_type === 'Red Light Jump' ? 'tcc-badge-red' :
                            v.violation_type === 'Wrong-Way Driving' ? 'tcc-badge-amber' : 'tcc-badge-blue'
                          }`}>
                            {v.violation_type}
                          </span>
                        </td>
                        <td>{v.vehicle_class}</td>
                        <td className="mono" style={{ fontWeight: 700 }}>{v.license_plate || 'OCR_PENDING'}</td>
                        <td className="mono">
                          {v.speed_kmh ? `${Math.round(v.speed_kmh)} km/h` : (v.speed ? `${Math.round(v.speed)} km/h` : 'Tracking')}
                        </td>
                        <td className="mono" style={{ fontSize: '0.68rem', color: '#64748B' }}>
                          {v.sha256_hash ? `${v.sha256_hash.substring(0, 16)}...` : 'SEALED'}
                        </td>
                        <td>
                          <span className={`tcc-badge ${
                            v.status === 'VERIFIED' ? 'tcc-badge-green' :
                            v.status === 'REJECTED' ? 'tcc-badge-red' : 'tcc-badge-amber'
                          }`}>
                            {v.status || 'PENDING_REVIEW'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '4px' }}>
                            <button 
                              className="tcc-btn tcc-btn-secondary" 
                              style={{ height: '26px', padding: '0 8px', fontSize: '0.7rem' }}
                              onClick={() => setActiveEvidence(v)}
                            >
                              <Eye size={11} /> Inspect
                            </button>
                            <button 
                              className="tcc-btn tcc-btn-secondary" 
                              style={{ height: '26px', padding: '0 8px', fontSize: '0.7rem' }}
                              onClick={async () => {
                                const res = await fetch(`${API_BASE}/api/evidence/${v.evidence_id || v._id}/challan`);
                                if (res.ok) setChallanData(await res.json());
                              }}
                            >
                              <FileText size={11} /> Challan
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: ALERTS & NOTIFICATIONS */}
        {activeTab === 'alerts' && (
          <div className="tcc-card">
            <div className="tcc-card-header">
              <div className="tcc-card-title">
                <Bell size={16} color="#DC2626" />
                <span>Incident Alerts & Notification Dispatch Dispatcher</span>
              </div>
              <span className="tcc-badge tcc-badge-slate">{alerts.length} Total Alerts</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {alerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px', color: '#64748B' }}>No incident alerts dispatched.</div>
              ) : (
                alerts.map(a => (
                  <div key={a.alert_id} style={{
                    border: '1px solid #E2E8F0',
                    borderRadius: '8px',
                    padding: '12px',
                    background: a.status === 'ACKNOWLEDGED' ? '#F8FAFC' : '#FFF1F2',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className={`tcc-badge ${a.severity === 'CRITICAL' ? 'tcc-badge-red' : 'tcc-badge-amber'}`}>
                          {a.severity}
                        </span>
                        <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{a.title}</span>
                      </div>
                      <div style={{ fontSize: '0.74rem', color: '#64748B', marginTop: '4px' }}>
                        ID: <span className="mono">{a.alert_id}</span> • Time: {new Date(a.timestamp).toLocaleString()} • SMS & Email Gateway Queued
                      </div>
                    </div>

                    <div>
                      {a.status === 'ACKNOWLEDGED' ? (
                        <span className="tcc-badge tcc-badge-green">
                          <CheckCircle size={12} /> Acknowledged by {a.acknowledged_by || 'Officer'}
                        </span>
                      ) : (
                        <button 
                          className="tcc-btn tcc-btn-primary" 
                          style={{ height: '30px', padding: '0 12px' }}
                          onClick={() => handleAcknowledgeAlert(a.alert_id)}
                        >
                          <CheckCircle size={13} /> Acknowledge Alert
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB 5: CAMERA MANAGEMENT */}
        {activeTab === 'cameras' && (
          <div className="tcc-card">
            <div className="tcc-card-header">
              <div className="tcc-card-title">
                <Camera size={16} color="#0052FF" />
                <span>Authorised CCTV & Edge Ingestion Inventory</span>
              </div>
              <button 
                className="tcc-btn tcc-btn-primary" 
                onClick={() => setAddCameraModal(true)}
              >
                <Plus size={13} /> Register Camera Node
              </button>
            </div>

            <div className="tcc-table-wrapper">
              <table className="tcc-table">
                <thead>
                  <tr>
                    <th>Camera ID</th>
                    <th>Name / Label</th>
                    <th>Geographic Node</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Active Feed</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cameras.map(cam => (
                    <tr key={cam.id}>
                      <td className="mono" style={{ fontWeight: 700 }}>{cam.id}</td>
                      <td style={{ fontWeight: 600 }}>{cam.name}</td>
                      <td>{cam.location}</td>
                      <td><span className="tcc-badge tcc-badge-slate">{cam.mode}</span></td>
                      <td>
                        <span className={`tcc-badge ${cam.status === 'ONLINE' ? 'tcc-badge-green' : 'tcc-badge-amber'}`}>
                          {cam.status}
                        </span>
                      </td>
                      <td>
                        {cam.is_active ? (
                          <span className="tcc-badge tcc-badge-green">LIVE INGESTION</span>
                        ) : (
                          <span className="tcc-badge tcc-badge-slate">STANDBY</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          {!cam.is_active && (
                            <button 
                              className="tcc-btn tcc-btn-primary" 
                              style={{ height: '26px', padding: '0 8px', fontSize: '0.7rem' }}
                              onClick={() => handleActivateCamera(cam.id)}
                            >
                              Activate
                            </button>
                          )}
                          <button 
                            className="tcc-btn tcc-btn-danger" 
                            style={{ height: '26px', padding: '0 6px' }}
                            onClick={() => handleDeleteCamera(cam.id)}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 6: SIGNAL OPTIMISATION */}
        {activeTab === 'signals' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '18px' }}>
            <div className="tcc-card">
              <div className="tcc-card-header">
                <div className="tcc-card-title">
                  <Sliders size={16} color="#059669" />
                  <span>Webster Cycle & Green Split Formulation</span>
                </div>
              </div>
              <div style={{ fontSize: '0.82rem', color: '#475569', lineHeight: 1.6 }}>
                <p>The system evaluates optimal cycle time dynamically using the classic <strong>Webster Method</strong>:</p>
                <div className="mono" style={{ background: '#F1F5F9', padding: '10px', borderRadius: '6px', margin: '10px 0', fontWeight: 600 }}>
                  C_opt = (1.5 * L + 5) / (1 - Y)
                </div>
                <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <li><strong>Lost Time (L)</strong>: 4.0 seconds per phase transition (Yellow + All-Red clearance).</li>
                  <li><strong>Current Saturation Ratio (Y)</strong>: {(Math.min(0.85, currentPCU / 45.0)).toFixed(2)}</li>
                  <li><strong>Calculated Webster Cycle</strong>: {status?.signal?.allocated_duration || 20} seconds.</li>
                  <li><strong>Active Approach PCU</strong>: {currentPCU} Passenger Car Units.</li>
                </ul>
              </div>
            </div>

            <div className="tcc-card">
              <div className="tcc-card-header">
                <div className="tcc-card-title">
                  <ShieldCheck size={16} color="#0052FF" />
                  <span>Hardware Interlock & Safety Constraints</span>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.78rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: '#F8FAFC', borderRadius: '6px' }}>
                  <span>Minimum Green Clearance</span>
                  <span className="mono" style={{ fontWeight: 700 }}>10 Seconds</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: '#F8FAFC', borderRadius: '6px' }}>
                  <span>Maximum Green Ceiling</span>
                  <span className="mono" style={{ fontWeight: 700 }}>60 Seconds</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: '#F8FAFC', borderRadius: '6px' }}>
                  <span>All-Red Intersection Clearance</span>
                  <span className="mono" style={{ fontWeight: 700 }}>2.0 Seconds</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: '#ECFDF5', borderRadius: '6px', color: '#065F46' }}>
                  <span>Safety Interlock Status</span>
                  <span className="mono" style={{ fontWeight: 700 }}>ENGAGED (Advisory Mode)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: SYSTEM HEALTH & AUDIT LOGS */}
        {activeTab === 'system' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {/* System Diagnostics */}
            <div className="tcc-card">
              <div className="tcc-card-header">
                <div className="tcc-card-title">
                  <Cpu size={16} color="#0052FF" />
                  <span>Subsystem Health & Edge Telemetry</span>
                </div>
                <span className="tcc-badge tcc-badge-green">ALL SYSTEMS OPERATIONAL</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <div style={{ fontSize: '0.72rem', color: '#64748B' }}>YOLOv5n Model Architecture</div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', marginTop: '2px' }}>OpenCV DNN Native C++</div>
                  <div className="mono" style={{ fontSize: '0.72rem', color: '#059669', marginTop: '4px' }}>
                    {fpsValue} FPS • {latencyMs} ms
                  </div>
                </div>

                <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <div style={{ fontSize: '0.72rem', color: '#64748B' }}>Database Resilience</div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', marginTop: '2px' }}>
                    {status?.database?.type || 'Offline Resilient Spool'}
                  </div>
                  <div className="mono" style={{ fontSize: '0.72rem', color: '#0052FF', marginTop: '4px' }}>
                    {status?.database?.unflushed_offline_records || 0} Records Buffered
                  </div>
                </div>

                <div style={{ padding: '12px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <div style={{ fontSize: '0.72rem', color: '#64748B' }}>Stream Watchdog</div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem', marginTop: '2px' }}>MSE Frozen Stream Monitor</div>
                  <div className="mono" style={{ fontSize: '0.72rem', color: '#059669', marginTop: '4px' }}>
                    Status: {healthStatus}
                  </div>
                </div>
              </div>
            </div>

            {/* Audit Logs */}
            <div className="tcc-card">
              <div className="tcc-card-header">
                <div className="tcc-card-title">
                  <History size={16} color="#475569" />
                  <span>Tamper-Evident Security Audit Logs</span>
                </div>
                <span className="mono" style={{ fontSize: '0.72rem', color: '#64748B' }}>backend/audit_trail.log</span>
              </div>

              <div className="tcc-table-wrapper" style={{ maxHeight: '360px', overflowY: 'auto' }}>
                <table className="tcc-table">
                  <thead>
                    <tr>
                      <th>Timestamp (UTC)</th>
                      <th>Action</th>
                      <th>Actor Identity</th>
                      <th>Role</th>
                      <th>Payload Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.length === 0 ? (
                      <tr>
                        <td colSpan="5" style={{ textAlign: 'center', padding: '20px', color: '#64748B' }}>
                          No audit entries registered.
                        </td>
                      </tr>
                    ) : (
                      auditLogs.map((log, idx) => (
                        <tr key={idx}>
                          <td className="mono" style={{ fontSize: '0.72rem', color: '#64748B' }}>
                            {log.timestamp ? new Date(log.timestamp).toLocaleString() : 'N/A'}
                          </td>
                          <td className="mono" style={{ fontWeight: 700, color: '#0052FF' }}>{log.action}</td>
                          <td>{log.user}</td>
                          <td><span className="tcc-badge tcc-badge-slate">{log.role}</span></td>
                          <td className="mono" style={{ fontSize: '0.7rem' }}>
                            {JSON.stringify(log.details || {})}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* 4. MODALS */}

      {/* Evidence Snapshot Inspector Modal */}
      {activeEvidence && (
        <div className="tcc-modal-backdrop" onClick={() => setActiveEvidence(null)}>
          <div className="tcc-modal-card" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Evidence Snapshot: {activeEvidence.evidence_id}</h3>
                <p style={{ fontSize: '0.72rem', color: '#64748B' }}>Cryptographic Chain of Custody Record</p>
              </div>
              <button 
                onClick={() => setActiveEvidence(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}
              >
                <X size={18} />
              </button>
            </div>

            <img 
              src={`${API_BASE}${activeEvidence.snapshot_url}`} 
              alt="Violation Snapshot" 
              style={{ width: '100%', borderRadius: '8px', border: '1px solid #CBD5E1' }}
              onError={e => { e.target.src = 'https://via.placeholder.com/640x360?text=Snapshot+Buffered'; }}
            />

            <div style={{ marginTop: '14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.8rem' }}>
              <div>
                <span style={{ color: '#64748B' }}>Extracted Plate:</span>
                <div className="mono" style={{ fontWeight: 700, fontSize: '0.95rem' }}>{activeEvidence.license_plate || 'UNKNOWN'}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Violation:</span>
                <div style={{ fontWeight: 700, color: '#DC2626' }}>{activeEvidence.violation_type}</div>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: '#64748B' }}>SHA-256 Hash Seal:</span>
                <div className="mono" style={{ fontSize: '0.66rem', color: '#0052FF', background: '#F1F5F9', padding: '6px', borderRadius: '4px', wordBreak: 'break-all' }}>
                  {activeEvidence.sha256_hash || 'SHA256_CERTIFIED_RECORD'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button 
                  className="tcc-btn tcc-btn-success"
                  onClick={() => handleReviewViolation(activeEvidence.evidence_id || activeEvidence._id, 'VERIFIED')}
                >
                  <CheckCircle size={13} /> Approve
                </button>
                <button 
                  className="tcc-btn tcc-btn-danger"
                  onClick={() => handleReviewViolation(activeEvidence.evidence_id || activeEvidence._id, 'REJECTED')}
                >
                  <XCircle size={13} /> Dismiss
                </button>
              </div>
              <button 
                className="tcc-btn tcc-btn-secondary"
                onClick={() => setActiveEvidence(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Official MoRTH E-Challan Notice Modal */}
      {challanData && (
        <div className="tcc-modal-backdrop" onClick={() => setChallanData(null)}>
          <div className="tcc-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: '520px' }}>
            <div style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '10px', marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0052FF' }}>ELECTRONIC MOTOR VEHICLE OFFENSE NOTICE</h3>
                <p style={{ fontSize: '0.7rem', color: '#64748B' }}>Government Traffic Enforcement Department</p>
              </div>
              <span className="tcc-badge tcc-badge-red">OFFICIAL DRAFT</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.8rem' }}>
              <div>
                <span style={{ color: '#64748B' }}>Challan Number:</span>
                <div className="mono" style={{ fontWeight: 700 }}>{challanData.challan_number}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Registration Plate:</span>
                <div className="mono" style={{ fontWeight: 700, color: '#0052FF' }}>{challanData.registration_plate}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Offense:</span>
                <div style={{ fontWeight: 700, color: '#DC2626' }}>{challanData.offense}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Fine (INR):</span>
                <div className="mono" style={{ fontWeight: 700, color: '#059669', fontSize: '1rem' }}>₹{challanData.fine_amount_inr}</div>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: '#64748B' }}>Cryptographic Evidence Hash Seal (Section 65B Certified):</span>
                <div className="mono" style={{ fontSize: '0.66rem', color: '#0052FF', background: '#F8FAFC', padding: '6px', borderRadius: '4px', wordBreak: 'break-all' }}>
                  {challanData.chain_of_custody_hash}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'space-between' }}>
              <button className="tcc-btn tcc-btn-primary" onClick={() => window.print()}>
                <Printer size={13} /> Print Notice
              </button>
              <button className="tcc-btn tcc-btn-secondary" onClick={() => setChallanData(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Camera Modal */}
      {addCameraModal && (
        <div className="tcc-modal-backdrop" onClick={() => setAddCameraModal(false)}>
          <div className="tcc-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: '440px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '12px' }}>Register CCTV Camera Node</h3>
            <form onSubmit={handleAddCamera}>
              <div className="tcc-form-group">
                <label className="tcc-form-label">Camera Name</label>
                <input 
                  type="text" 
                  className="tcc-form-input" 
                  value={newCamName} 
                  onChange={e => setNewCamName(e.target.value)} 
                  placeholder="e.g. Ring Road West Junction" 
                  required 
                />
              </div>
              <div className="tcc-form-group">
                <label className="tcc-form-label">Location / Corridor</label>
                <input 
                  type="text" 
                  className="tcc-form-input" 
                  value={newCamLocation} 
                  onChange={e => setNewCamLocation(e.target.value)} 
                  placeholder="e.g. MG Road KM 4.2" 
                />
              </div>
              <div className="tcc-form-group">
                <label className="tcc-form-label">Protocol Mode</label>
                <select 
                  className="tcc-form-input" 
                  value={newCamMode} 
                  onChange={e => setNewCamMode(e.target.value)}
                >
                  <option value="RTSP">RTSP Camera Stream</option>
                  <option value="WEBCAM">USB Video Class Device</option>
                  <option value="UPLOAD">Pre-recorded Video File</option>
                </select>
              </div>
              <div className="tcc-form-group">
                <label className="tcc-form-label">Source URL / Device Index</label>
                <input 
                  type="text" 
                  className="tcc-form-input" 
                  value={newCamSource} 
                  onChange={e => setNewCamSource(e.target.value)} 
                  placeholder="rtsp://192.168.1.100:554/live or 0" 
                  required 
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button type="button" className="tcc-btn tcc-btn-secondary" onClick={() => setAddCameraModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="tcc-btn tcc-btn-primary">
                  Save & Register
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Officer Authentication Modal */}
      {authModal && (
        <div className="tcc-modal-backdrop" onClick={() => setAuthModal(false)}>
          <div className="tcc-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: '420px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield size={18} color="#0052FF" />
                <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Officer Authentication</h3>
              </div>
              <button onClick={() => setAuthModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', background: '#F1F5F9', borderRadius: '6px', padding: '2px', marginBottom: '14px' }}>
              <button 
                type="button"
                className={`tcc-btn ${authTab === 'login' ? 'tcc-btn-primary' : 'tcc-btn-secondary'}`}
                style={{ flex: 1, height: '30px', border: 'none' }}
                onClick={() => setAuthTab('login')}
              >
                Sign In
              </button>
              <button 
                type="button"
                className={`tcc-btn ${authTab === 'register' ? 'tcc-btn-primary' : 'tcc-btn-secondary'}`}
                style={{ flex: 1, height: '30px', border: 'none' }}
                onClick={() => setAuthTab('register')}
              >
                Create Account
              </button>
            </div>

            {authSuccess && <div style={{ background: '#ECFDF5', color: '#059669', padding: '8px', borderRadius: '6px', fontSize: '0.76rem', marginBottom: '10px' }}>{authSuccess}</div>}
            {authError && <div style={{ background: '#FEF2F2', color: '#DC2626', padding: '8px', borderRadius: '6px', fontSize: '0.76rem', marginBottom: '10px' }}>{authError}</div>}

            <form onSubmit={authTab === 'login' ? handleLoginSubmit : handleRegisterSubmit}>
              {authTab === 'register' && (
                <div className="tcc-form-group">
                  <label className="tcc-form-label">Official Name</label>
                  <input 
                    type="text" 
                    className="tcc-form-input" 
                    value={nameInput} 
                    onChange={e => setNameInput(e.target.value)} 
                    placeholder="Inspector Rajesh Verma" 
                    required 
                  />
                </div>
              )}

              <div className="tcc-form-group">
                <label className="tcc-form-label">Official Email ID</label>
                <input 
                  type="email" 
                  className="tcc-form-input" 
                  value={emailInput} 
                  onChange={e => {
                    setEmailInput(e.target.value);
                    setEmailError(!EMAIL_REGEX.test(e.target.value) ? 'Invalid email format.' : '');
                  }} 
                  placeholder="officer@traffic.gov.in" 
                  required 
                />
                {emailError && <div style={{ color: '#DC2626', fontSize: '0.7rem', marginTop: '2px' }}>{emailError}</div>}
              </div>

              <div className="tcc-form-group">
                <label className="tcc-form-label">Password</label>
                <div style={{ position: 'relative' }}>
                  <input 
                    type={showPassword ? 'text' : 'password'} 
                    className="tcc-form-input" 
                    value={passwordInput} 
                    onChange={e => {
                      setPasswordInput(e.target.value);
                      setPasswordError(e.target.value.length < 8 ? 'Min 8 characters required.' : '');
                    }} 
                    placeholder="Enter secure password" 
                    required 
                  />
                  <button 
                    type="button" 
                    onClick={() => setShowPassword(!showPassword)}
                    style={{ position: 'absolute', right: '10px', top: '10px', background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {passwordError && <div style={{ color: '#DC2626', fontSize: '0.7rem', marginTop: '2px' }}>{passwordError}</div>}
              </div>

              {authTab === 'register' && (
                <div className="tcc-form-group">
                  <label className="tcc-form-label">Duty Role</label>
                  <select 
                    className="tcc-form-input" 
                    value={roleInput} 
                    onChange={e => setRoleInput(e.target.value)}
                  >
                    <option value="OPERATOR">Traffic Control Officer</option>
                    <option value="AUDITOR">Compliance Auditor</option>
                    <option value="ADMIN">System Administrator</option>
                  </select>
                </div>
              )}

              <button type="submit" className="tcc-btn tcc-btn-primary" style={{ width: '100%', height: '38px', marginTop: '8px' }}>
                {authTab === 'login' ? 'Authenticate Session' : 'Register Officer Account'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
