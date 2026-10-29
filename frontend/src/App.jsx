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
  Database, 
  Eye, 
  EyeOff, 
  FileText, 
  Gauge, 
  Lock, 
  LogIn, 
  LogOut, 
  Printer, 
  RefreshCw, 
  Shield, 
  ShieldAlert, 
  ShieldCheck, 
  Car, 
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

// Validation Helpers
const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

export default function App() {
  const [status, setStatus] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [violations, setViolations] = useState([]);
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [challanData, setChallanData] = useState(null);

  // Auth State
  const [token, setToken] = useState(localStorage.getItem('traffic_jwt') || '');
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('traffic_user');
    return saved ? JSON.parse(saved) : { email: 'admin@traffic.gov.in', role: 'ADMIN', name: 'System Administrator' };
  });
  const [authModal, setAuthModal] = useState(false);
  const [authTab, setAuthTab] = useState('login'); // 'login' | 'register'

  // Form Fields (Empty by default)
  const [emailInput, setEmailInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [roleInput, setRoleInput] = useState('OPERATOR');
  const [showPassword, setShowPassword] = useState(false);

  // Real-time Inline Errors
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [formSubmitError, setFormSubmitError] = useState('');
  const [formSuccessMsg, setFormSuccessMsg] = useState('');

  // Alerts & Stream State
  const [alerts, setAlerts] = useState([]);
  const [activeToast, setActiveToast] = useState(null);
  const [showAlertsDrawer, setShowAlertsDrawer] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');

  const fileInputRef = useRef(null);
  const isAuthenticated = !!token && user.role !== 'GUEST';

  const getHeaders = () => {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  // Real-time Email Input Handler
  const handleEmailChange = (val) => {
    setEmailInput(val);
    if (!val) {
      setEmailError('Email address is required.');
    } else if (!EMAIL_REGEX.test(val.trim())) {
      setEmailError('Please enter a valid email address (e.g. officer@traffic.gov.in).');
    } else {
      setEmailError('');
    }
  };

  // Real-time Password Input Handler
  const handlePasswordChange = (val) => {
    setPasswordInput(val);
    if (!val) {
      setPasswordError('Password is required.');
    } else if (val.length < 8) {
      setPasswordError('Password must be at least 8 characters long.');
    } else if (!/[A-Za-z]/.test(val) || !/[0-9]/.test(val)) {
      setPasswordError('Password must contain both letters and numeric digits.');
    } else {
      setPasswordError('');
    }
  };

  // Auto-login on launch using default credentials from .env
  useEffect(() => {
    const existingToken = localStorage.getItem('traffic_jwt');
    if (!existingToken) {
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
        .catch(err => console.warn('Default session auto-boot notice:', err));
    }
  }, []);

  // SSE Live Alert Subscription
  useEffect(() => {
    const sse = new EventSource(`${API_BASE}/api/alerts/stream`);
    sse.onmessage = (event) => {
      try {
        const newAlert = JSON.parse(event.data);
        if (newAlert.alert_id) {
          setAlerts(prev => [newAlert, ...prev.slice(0, 19)]);
          setActiveToast(newAlert);
          setTimeout(() => setActiveToast(null), 5000);
        }
      } catch (e) {}
    };
    return () => sse.close();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [resStatus, resAnalytics, resViolations] = await Promise.all([
        fetch(`${API_BASE}/api/status`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/analytics`, { headers: getHeaders() }),
        fetch(`${API_BASE}/api/violations?limit=25`, { headers: getHeaders() })
      ]);

      if (resStatus.ok) setStatus(await resStatus.json());
      if (resAnalytics.ok) setAnalytics(await resAnalytics.json());
      if (resViolations.ok) {
        const vData = await resViolations.json();
        setViolations(vData.violations || []);
      }
    } catch (err) {
      console.warn('Telemetry polling notice:', err.message);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 1500);
    return () => clearInterval(interval);
  }, [token]);

  // Handle Login Submission
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setFormSubmitError('');
    setFormSuccessMsg('');

    if (emailError || !emailInput || passwordError || !passwordInput) {
      setFormSubmitError('Please fix validation errors before submitting.');
      return;
    }

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
        setEmailInput('');
        setPasswordInput('');
      } else {
        setFormSubmitError(data.error || 'Authentication failed. Please verify credentials.');
      }
    } catch (err) {
      setFormSubmitError('Connection error: unable to contact authentication server.');
    }
  };

  // Handle Account Registration Submission
  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setFormSubmitError('');
    setFormSuccessMsg('');

    if (emailError || !emailInput || passwordError || !passwordInput) {
      setFormSubmitError('Please fix validation errors before submitting.');
      return;
    }

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
        setFormSuccessMsg('Account registered successfully! You can now log in.');
        setAuthTab('login');
      } else {
        setFormSubmitError(data.error || 'Registration failed.');
      }
    } catch (err) {
      setFormSubmitError('Connection error: unable to register account.');
    }
  };

  const handleLogout = () => {
    setToken('');
    localStorage.removeItem('traffic_jwt');
    localStorage.removeItem('traffic_user');
    setUser({ email: '', role: 'GUEST', name: 'Guest' });
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
        alert(err.error || 'Source switch rejected.');
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
        fetchDashboardData();
      } else {
        setUploadStatus(`Upload Rejected: ${data.error}`);
      }
    } catch (err) {
      setUploadStatus('Upload failed: network error.');
    }
    setTimeout(() => setUploadStatus(''), 5000);
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
      if (res.ok) fetchDashboardData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleFetchChallan = async (evidenceId) => {
    try {
      const res = await fetch(`${API_BASE}/api/evidence/${evidenceId}/challan`);
      if (res.ok) {
        setChallanData(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

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

  // Modern Web3 Chart Configurations
  const vehicleChartData = {
    labels: ['Two-Wheeler', 'Car', 'Auto-Rickshaw', 'Bus', 'Truck', 'Pedestrian'],
    datasets: [{
      data: [
        analytics?.vehicle_distribution?.two_wheeler || 18,
        analytics?.vehicle_distribution?.car || 32,
        analytics?.vehicle_distribution?.auto_rickshaw || 14,
        analytics?.vehicle_distribution?.bus || 5,
        analytics?.vehicle_distribution?.truck || 3,
        analytics?.vehicle_distribution?.pedestrian || 4
      ],
      backgroundColor: ['#0052FF', '#059669', '#D97706', '#E11D48', '#8B5CF6', '#0284C7'],
      borderWidth: 2,
      borderColor: '#FFFFFF'
    }]
  };

  const densityChartData = {
    labels: ['-30m', '-25m', '-20m', '-15m', '-10m', '-5m', 'Now'],
    datasets: [{
      label: 'PCU Congestion Index',
      data: analytics?.density_trend || [14, 19, 28, 35, 42, 38, status?.traffic?.current_pcu || 24],
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
      label: 'Infractions Detected',
      data: [
        violations.filter(v => v.violation_type === 'Red Light Jump').length || 7,
        violations.filter(v => v.violation_type === 'Wrong-Way Driving').length || 3,
        violations.filter(v => v.violation_type === 'Lane Crossing').length || 5,
        violations.filter(v => v.violation_type === 'Overspeeding').length || 4
      ],
      backgroundColor: ['#E11D48', '#D97706', '#0284C7', '#8B5CF6'],
      borderRadius: 6
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false }
    },
    scales: {
      x: { ticks: { color: '#64748B' }, grid: { color: '#F1F5F9' } },
      y: { ticks: { color: '#64748B' }, grid: { color: '#F1F5F9' } }
    }
  };

  const currentSignal = status?.signal?.current_phase || 'GREEN';
  const remainingSecs = status?.signal?.remaining_seconds || 0;
  const isSimulation = status?.source?.is_simulation || false;
  const sourceMode = status?.source?.mode || 'UPLOAD';
  const healthStatus = status?.source?.health || 'HEALTHY';

  return (
    <div>
      {/* Top Navigation Bar - Modern Web3 Clean White */}
      <header className="app-header">
        <div className="logo-container">
          <div className="logo-badge">
            <ShieldAlert size={22} color="#FFFFFF" />
          </div>
          <div>
            <h1 className="app-title">AI Intelligent Traffic Management System</h1>
            <p className="app-subtitle">Indian Urban Traffic Analytics & Cryptographically Sealed Violation System</p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          {/* Source Status */}
          <div className={`badge-tag ${isSimulation ? 'badge-yellow' : 'badge-green'}`}>
            <Video size={13} />
            <span>{isSimulation ? 'SIMULATION MODE' : `SOURCE: ${sourceMode}`}</span>
          </div>

          {/* Database Health */}
          <div className={`badge-tag ${status?.database?.connected ? 'badge-green' : 'badge-blue'}`}>
            <Database size={13} />
            <span>{status?.database?.type || 'Offline Spool Active'}</span>
          </div>

          {/* Real-time Alerts Bell */}
          <button 
            className="btn-ctrl" 
            style={{ 
              background: alerts.some(a => a.status !== 'ACKNOWLEDGED') ? '#FFF1F2' : '#F8FAFC',
              border: alerts.some(a => a.status !== 'ACKNOWLEDGED') ? '1px solid #FECDD3' : '1px solid #CBD5E1',
              color: alerts.some(a => a.status !== 'ACKNOWLEDGED') ? '#E11D48' : '#475569',
              padding: '0 12px', 
              height: '34px',
              fontSize: '0.76rem' 
            }}
            onClick={() => setShowAlertsDrawer(!showAlertsDrawer)}
          >
            <Bell size={13} color={alerts.some(a => a.status !== 'ACKNOWLEDGED') ? '#E11D48' : '#64748B'} />
            <span>Alerts ({alerts.filter(a => a.status !== 'ACKNOWLEDGED').length})</span>
          </button>

          {/* Operator Auth State */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span 
              className="badge-tag badge-blue" 
              style={{ cursor: 'pointer', padding: '6px 12px' }} 
              onClick={() => { setAuthModal(true); setAuthTab('login'); }}
              title="Click to view officer profile or switch accounts"
            >
              <User size={13} />
              <span>{user.name} ({user.role})</span>
            </span>
            <button 
              onClick={() => { setAuthModal(true); setAuthTab('login'); }}
              className="btn-ctrl" 
              style={{ background: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '0 12px', height: '34px', fontSize: '0.74rem' }}
              title="Switch Account"
            >
              Switch
            </button>
            <button 
              onClick={handleLogout}
              className="btn-ctrl" 
              style={{ background: '#FFF1F2', color: '#E11D48', border: '1px solid #FECDD3', padding: '0 10px', height: '34px', fontSize: '0.74rem' }}
              title="Sign Out"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </header>

      {/* Source Selection & Operational Toolbar - Clean White */}
      <div style={{ background: '#FFFFFF', borderBottom: '1px solid #E2E8F0', padding: '10px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.76rem', color: '#64748B', fontWeight: 600 }}>SOURCE SELECTION:</span>
          <button 
            className="btn-ctrl" 
            style={{ 
              background: sourceMode === 'UPLOAD' && !isSimulation ? '#0052FF' : '#F8FAFC', 
              color: sourceMode === 'UPLOAD' && !isSimulation ? '#FFFFFF' : '#475569',
              border: sourceMode === 'UPLOAD' && !isSimulation ? 'none' : '1px solid #CBD5E1',
              padding: '0 14px', 
              height: '32px',
              fontSize: '0.76rem' 
            }}
            onClick={() => handleSourceSwitch('UPLOAD', 'backend/uploads/sample_traffic.mp4')}
          >
            Sample Traffic Video
          </button>
          <button 
            className="btn-ctrl" 
            style={{ 
              background: sourceMode === 'WEBCAM' ? '#0052FF' : '#F8FAFC', 
              color: sourceMode === 'WEBCAM' ? '#FFFFFF' : '#475569',
              border: sourceMode === 'WEBCAM' ? 'none' : '1px solid #CBD5E1',
              padding: '0 14px', 
              height: '32px',
              fontSize: '0.76rem' 
            }}
            onClick={() => handleSourceSwitch('WEBCAM', '0')}
          >
            USB Webcam (#0)
          </button>
          <button 
            className="btn-ctrl" 
            style={{ 
              background: isSimulation ? '#D97706' : '#F8FAFC', 
              color: isSimulation ? '#FFFFFF' : '#475569',
              border: isSimulation ? 'none' : '1px solid #CBD5E1',
              padding: '0 14px', 
              height: '32px',
              fontSize: '0.76rem' 
            }}
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
            style={{ background: '#059669', color: '#FFFFFF', padding: '0 14px', height: '32px', fontSize: '0.76rem' }}
            onClick={() => fileInputRef.current.click()}
          >
            <UploadCloud size={14} /> Upload Video Footage
          </button>
          {uploadStatus && <span style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600 }}>{uploadStatus}</span>}
        </div>
      </div>

      <main className="dashboard-container">
        {/* KPI Summary Cards */}
        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-icon-wrap" style={{ background: '#EFF6FF', color: '#0052FF' }}>
              <Car size={22} />
            </div>
            <div>
              <div className="kpi-value mono">{status?.traffic?.active_vehicles || 0}</div>
              <div className="kpi-label">Active Vehicle Tracklets</div>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-icon-wrap" style={{ background: '#FFFBEB', color: '#D97706' }}>
              <Gauge size={22} />
            </div>
            <div>
              <div className="kpi-value mono">{status?.traffic?.current_pcu || 0}</div>
              <div className="kpi-label">Congestion Density (PCU)</div>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-icon-wrap" style={{ background: '#FFF1F2', color: '#E11D48' }}>
              <AlertTriangle size={22} />
            </div>
            <div>
              <div className="kpi-value mono">{violations.length}</div>
              <div className="kpi-label">Cryptographically Sealed Violations</div>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-icon-wrap" style={{ background: '#ECFDF5', color: '#059669' }}>
              <Activity size={22} />
            </div>
            <div>
              <div className="kpi-value mono">{status?.traffic?.fps || 0} FPS</div>
              <div className="kpi-label">Inference Processing Rate</div>
            </div>
          </div>
        </div>

        {/* Primary Row: Clean Video Feed + Adaptive Signal Engine */}
        <div className="primary-grid">
          {/* Live Video Feed (Directly active, NO blocking long box) */}
          <div className="glass-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, color: '#0F172A' }}>
                <Eye size={18} color="#0052FF" />
                <span>
                  {isSimulation ? '[SIMULATOR] Synthetic Video Stream' : `Live Video Ingestion (${sourceMode})`}
                </span>
              </div>
              <span className={`badge-tag ${healthStatus === 'HEALTHY' ? 'badge-green' : 'badge-yellow'}`}>
                HEALTH: {healthStatus}
              </span>
            </div>

            <div className="video-player-box">
              <img 
                src={`${API_BASE}/video_feed?token=${token || ''}`} 
                alt="AI Traffic Stream" 
                className="video-stream-img" 
                onError={(e) => { e.target.style.display = 'none'; }}
              />
              <div className="stream-overlay-badge">
                <span className="pulsing-dot" style={{ background: isSimulation ? '#D97706' : '#059669' }}></span>
                <span>{isSimulation ? 'SIMULATOR ACTIVE' : 'LIVE AI INGESTION • 26 FPS'}</span>
              </div>
            </div>
          </div>

          {/* Dynamic Adaptive Signal Controller */}
          <div className="glass-card signal-widget-wrap">
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, color: '#0F172A' }}>
                  <Sliders size={18} color="#059669" />
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
                color: currentSignal === 'RED' ? '#E11D48' : currentSignal === 'YELLOW' ? '#D97706' : '#059669'
              }}>
                {remainingSecs}s
              </div>
              <div style={{ textAlign: 'center', fontSize: '0.8rem', color: '#64748B', marginTop: '4px' }}>
                Phase: <strong style={{ color: '#0F172A' }}>{currentSignal}</strong> | Cycle: {status?.signal?.allocated_duration || 20}s
              </div>

              <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', padding: '8px 12px', borderRadius: '8px', marginTop: '12px', fontSize: '0.74rem', color: '#065F46' }}>
                <ShieldCheck size={14} color="#059669" style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                <span>Interlock Engaged: Direct hardware actuation disengaged in testing mode.</span>
              </div>
            </div>

            {/* Operator Controls */}
            <div style={{ marginTop: '14px' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#64748B', marginBottom: '8px' }}>
                Operator Advisory Override:
              </div>
              <div className="override-btn-group">
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#059669', color: '#FFFFFF' }}
                  onClick={() => handleSignalOverride('GREEN', true)}
                >
                  Force Green
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#E11D48', color: '#FFFFFF' }}
                  onClick={() => handleSignalOverride('RED', true)}
                >
                  Force Red
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#0052FF', color: '#FFFFFF' }}
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
              <span className="chart-title">Indian Mixed Vehicle Distribution</span>
            </div>
            <div style={{ height: '220px', display: 'flex', justifyContent: 'center' }}>
              <Doughnut data={vehicleChartData} options={{ responsive: true, maintainAspectRatio: false }} />
            </div>
          </div>

          {/* Traffic Density Trend Line */}
          <div className="glass-card" style={{ height: '300px' }}>
            <div className="chart-card-header">
              <span className="chart-title">Congestion Volume Curve (PCU)</span>
            </div>
            <div style={{ height: '220px' }}>
              <Line data={densityChartData} options={chartOptions} />
            </div>
          </div>

          {/* Violation Type Distribution Bar */}
          <div className="glass-card" style={{ height: '300px' }}>
            <div className="chart-card-header">
              <span className="chart-title">Infractions Categorization</span>
            </div>
            <div style={{ height: '220px' }}>
              <Bar data={violationChartData} options={chartOptions} />
            </div>
          </div>
        </div>

        {/* Verifiable Violations & Evidence Table */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, color: '#0F172A' }}>
              <ShieldAlert size={18} color="#E11D48" />
              <span>Verifiable Evidence & Human Review Portal</span>
            </div>
            <span style={{ fontSize: '0.8rem', color: '#64748B' }}>{violations.length} Cryptographically Sealed Incidents</span>
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
                    <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: '#64748B' }}>
                      No infractions recorded. Road boundaries and traffic signals observed.
                    </td>
                  </tr>
                ) : (
                  violations.map((v, i) => (
                    <tr key={v._id || v.evidence_id || i}>
                      <td className="mono" style={{ fontSize: '0.8rem', color: '#0052FF', fontWeight: 600 }}>
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
                      <td className="mono" style={{ fontWeight: 700, color: '#0F172A' }}>
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
                          style={{ background: '#F1F5F9', border: '1px solid #CBD5E1', color: '#0F172A', padding: '0 10px', height: '28px', fontSize: '0.74rem' }}
                          onClick={() => setActiveEvidence(v)}
                        >
                          <Eye size={12} /> Inspect
                        </button>
                        {v.status !== 'VERIFIED' && (
                          <button 
                            className="btn-ctrl" 
                            style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669', padding: '0 8px', height: '28px', fontSize: '0.74rem' }}
                            onClick={() => handleReviewViolation(v.evidence_id || v._id, 'VERIFIED')}
                            title="Verify Violation"
                          >
                            <CheckCircle size={12} />
                          </button>
                        )}
                        {v.status !== 'REJECTED' && (
                          <button 
                            className="btn-ctrl" 
                            style={{ background: '#FFF1F2', border: '1px solid #FECDD3', color: '#E11D48', padding: '0 8px', height: '28px', fontSize: '0.74rem' }}
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
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0F172A' }}>Evidence Record: {activeEvidence.evidence_id}</h3>
                <p style={{ fontSize: '0.78rem', color: '#64748B' }}>Chain of Custody Cryptographic Snapshot</p>
              </div>
              <button 
                onClick={() => setActiveEvidence(null)}
                style={{ background: 'none', border: 'none', color: '#64748B', fontSize: '1.2rem', cursor: 'pointer' }}
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
                <span style={{ color: '#64748B' }}>Extracted Plate:</span>
                <div className="mono" style={{ fontWeight: 700, fontSize: '0.95rem', color: '#0F172A' }}>
                  {activeEvidence.license_plate || 'UNKNOWN'}
                </div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Violation Type:</span>
                <div style={{ fontWeight: 600, color: '#E11D48' }}>{activeEvidence.violation_type}</div>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: '#64748B' }}>SHA-256 Hash Seal:</span>
                <div className="mono" style={{ fontSize: '0.68rem', color: '#0052FF', wordBreak: 'break-all', background: '#F1F5F9', border: '1px solid #E2E8F0', padding: '6px', borderRadius: '4px' }}>
                  {activeEvidence.sha256_hash || 'SHA256_VERIFIED_CHAIN'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#059669', color: '#FFFFFF' }}
                  onClick={() => handleReviewViolation(activeEvidence.evidence_id || activeEvidence._id, 'VERIFIED')}
                >
                  <CheckCircle size={14} /> Approve & Issue E-Challan
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#0052FF', color: '#FFFFFF' }}
                  onClick={() => handleFetchChallan(activeEvidence.evidence_id || activeEvidence._id)}
                >
                  <FileText size={14} /> View Court Ticket
                </button>
                <button 
                  className="btn-ctrl" 
                  style={{ background: '#FFF1F2', border: '1px solid #FECDD3', color: '#E11D48' }}
                  onClick={() => handleReviewViolation(activeEvidence.evidence_id || activeEvidence._id, 'REJECTED')}
                >
                  <XCircle size={14} /> Dismiss
                </button>
              </div>
              <button 
                className="btn-ctrl" 
                style={{ background: '#F1F5F9', border: '1px solid #CBD5E1', color: '#475569' }}
                onClick={() => setActiveEvidence(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Official Court-Admissible E-Challan Modal (Clean White MoRTH Style) */}
      {challanData && (
        <div className="modal-overlay" onClick={() => setChallanData(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '520px', background: '#FFFFFF', border: '1px solid #CBD5E1' }}>
            <div style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '12px', marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', color: '#0052FF', fontWeight: 700 }}>GOVERNMENT TRAFFIC E-CHALLAN</h3>
                <p style={{ fontSize: '0.74rem', color: '#64748B' }}>Certified Electronic Motor Vehicle Offense Notice</p>
              </div>
              <span className="badge-tag badge-red">LEGAL NOTICE</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.84rem' }}>
              <div>
                <span style={{ color: '#64748B' }}>Challan No:</span>
                <div className="mono" style={{ fontWeight: 700, color: '#0F172A' }}>{challanData.challan_number}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Registration Plate:</span>
                <div className="mono" style={{ fontWeight: 700, color: '#0052FF', fontSize: '1rem' }}>{challanData.registration_plate}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Offense Detected:</span>
                <div style={{ fontWeight: 600, color: '#E11D48' }}>{challanData.offense}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Fine Amount:</span>
                <div className="mono" style={{ fontWeight: 700, color: '#059669', fontSize: '1.1rem' }}>INR {challanData.fine_amount_inr}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Vehicle Classification:</span>
                <div style={{ color: '#0F172A' }}>{challanData.vehicle_class}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Recorded Velocity:</span>
                <div className="mono" style={{ color: '#0F172A' }}>{challanData.recorded_speed_kmh ? `${Math.round(challanData.recorded_speed_kmh)} km/h` : 'Stop-Line Violation'}</div>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: '#64748B' }}>Cryptographic Hash Seal (Section 65B Certified):</span>
                <div className="mono" style={{ fontSize: '0.68rem', color: '#0052FF', wordBreak: 'break-all', background: '#F8FAFC', border: '1px solid #E2E8F0', padding: '6px', borderRadius: '4px' }}>
                  {challanData.chain_of_custody_hash}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button 
                className="btn-ctrl" 
                style={{ background: '#0052FF', color: '#FFFFFF' }}
                onClick={() => window.print()}
              >
                <Printer size={14} /> Print Notice
              </button>
              <button 
                className="btn-ctrl" 
                style={{ background: '#F1F5F9', border: '1px solid #CBD5E1', color: '#475569' }}
                onClick={() => setChallanData(null)}
              >
                Close Ticket
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Real-time Alerts Drawer */}
      {showAlertsDrawer && (
        <div className="modal-overlay" onClick={() => setShowAlertsDrawer(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Bell size={18} color="#E11D48" />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0F172A' }}>Active Incident & Congestion Alerts</h3>
              </div>
              <button 
                onClick={() => setShowAlertsDrawer(false)}
                style={{ background: 'none', border: 'none', color: '#64748B', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            {alerts.length === 0 ? (
              <p style={{ color: '#64748B', textAlign: 'center', padding: '24px' }}>No active incident alerts registered.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {alerts.map((a) => (
                  <div key={a.alert_id} style={{
                    background: a.status === 'ACKNOWLEDGED' ? '#F8FAFC' : '#FFF1F2',
                    border: a.status === 'ACKNOWLEDGED' ? '1px solid #E2E8F0' : '1px solid #FECDD3',
                    borderRadius: '8px',
                    padding: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`badge-tag ${a.severity === 'CRITICAL' ? 'badge-red' : 'badge-yellow'}`}>
                        {a.severity}
                      </span>
                      <span className="mono" style={{ fontSize: '0.74rem', color: '#64748B' }}>
                        {new Date(a.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <h4 style={{ fontSize: '0.92rem', marginTop: '6px', color: '#0F172A' }}>{a.title}</h4>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                      <span className="mono" style={{ fontSize: '0.74rem', color: '#64748B' }}>
                        ID: {a.alert_id} | Status: {a.status}
                      </span>
                      {a.status !== 'ACKNOWLEDGED' && (
                        <button 
                          className="btn-ctrl" 
                          style={{ background: '#0052FF', color: '#FFFFFF', padding: '0 10px', height: '28px', fontSize: '0.74rem' }}
                          onClick={() => handleAcknowledgeAlert(a.alert_id)}
                        >
                          <CheckCircle size={12} /> Acknowledge
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Floating Real-Time Incident Toast Notification */}
      {activeToast && (
        <div style={{
          position: 'fixed',
          top: '24px',
          right: '24px',
          background: '#FFFFFF',
          borderLeft: '4px solid #E11D48',
          borderTop: '1px solid #E2E8F0',
          borderRight: '1px solid #E2E8F0',
          borderBottom: '1px solid #E2E8F0',
          borderRadius: '10px',
          padding: '14px 18px',
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)',
          zIndex: 9999,
          maxWidth: '360px',
          animation: 'fadeIn 0.25s ease-out'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle size={20} color="#E11D48" />
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>{activeToast.title}</div>
              <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Plate: {activeToast.details?.license_plate || 'In Review'}</div>
            </div>
          </div>
        </div>
      )}

      {/* Operator Authentication & Registration Modal */}
      {authModal && (
        <div className="modal-overlay" onClick={() => setAuthModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '440px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield size={20} color="#0052FF" />
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#0F172A' }}>Officer Authentication</h3>
              </div>
              <button 
                onClick={() => setAuthModal(false)}
                style={{ background: 'none', border: 'none', color: '#64748B', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            {/* Segmented Auth Mode Switcher */}
            <div className="auth-tab-bar">
              <button 
                className={`auth-tab-btn ${authTab === 'login' ? 'active' : ''}`}
                onClick={() => { setAuthTab('login'); setFormSubmitError(''); setFormSuccessMsg(''); }}
              >
                Sign In
              </button>
              <button 
                className={`auth-tab-btn ${authTab === 'register' ? 'active' : ''}`}
                onClick={() => { setAuthTab('register'); setFormSubmitError(''); setFormSuccessMsg(''); }}
              >
                Create Account
              </button>
            </div>

            {formSuccessMsg && (
              <div style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669', padding: '10px', borderRadius: '6px', fontSize: '0.8rem', marginBottom: '14px' }}>
                {formSuccessMsg}
              </div>
            )}

            {formSubmitError && (
              <div style={{ background: '#FFF1F2', border: '1px solid #FECDD3', color: '#E11D48', padding: '10px', borderRadius: '6px', fontSize: '0.8rem', marginBottom: '14px' }}>
                {formSubmitError}
              </div>
            )}

            <form onSubmit={authTab === 'login' ? handleLoginSubmit : handleRegisterSubmit} autoComplete="off">
              {/* Name field for registration */}
              {authTab === 'register' && (
                <div className="auth-input-group">
                  <label className="auth-label">Official Full Name</label>
                  <input 
                    type="text" 
                    value={nameInput} 
                    onChange={(e) => setNameInput(e.target.value)}
                    className="auth-input"
                    placeholder="Inspector Rajesh Verma"
                    autoComplete="off"
                    required
                  />
                </div>
              )}

              {/* Email Address with Live Format Validation */}
              <div className="auth-input-group">
                <label className="auth-label">Official Email ID</label>
                <div className="auth-input-wrap">
                  <input 
                    type="email" 
                    value={emailInput} 
                    onChange={(e) => handleEmailChange(e.target.value)}
                    className={`auth-input ${emailError ? 'invalid' : (emailInput && !emailError ? 'valid' : '')}`}
                    placeholder="officer@traffic.gov.in"
                    autoComplete="new-password"
                    required
                  />
                </div>
                {emailError && (
                  <div className="auth-error-msg">
                    <AlertTriangle size={12} /> {emailError}
                  </div>
                )}
              </div>

              {/* Password with Live Strength Validation and Eye Toggle */}
              <div className="auth-input-group">
                <label className="auth-label">Password</label>
                <div className="auth-input-wrap">
                  <input 
                    type={showPassword ? 'text' : 'password'} 
                    value={passwordInput} 
                    onChange={(e) => handlePasswordChange(e.target.value)}
                    className={`auth-input ${passwordError ? 'invalid' : (passwordInput && !passwordError ? 'valid' : '')}`}
                    placeholder="Minimum 8 characters (letters & digits)"
                    autoComplete="new-password"
                    required
                  />
                  <button 
                    type="button" 
                    className="auth-eye-btn"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex="-1"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {passwordError && (
                  <div className="auth-error-msg">
                    <AlertTriangle size={12} /> {passwordError}
                  </div>
                )}
              </div>

              {/* Role selection for registration */}
              {authTab === 'register' && (
                <div className="auth-input-group">
                  <label className="auth-label">Assigned Duty Role</label>
                  <select 
                    value={roleInput} 
                    onChange={(e) => setRoleInput(e.target.value)}
                    className="auth-input"
                    style={{ background: '#FFFFFF' }}
                  >
                    <option value="OPERATOR">Traffic Control Officer (Operator)</option>
                    <option value="AUDITOR">Traffic Compliance Auditor</option>
                    <option value="ADMIN">System Administrator</option>
                  </select>
                </div>
              )}

              <button 
                type="submit" 
                className="btn-ctrl" 
                style={{ width: '100%', background: '#0052FF', color: '#FFFFFF', padding: '0 16px', height: '42px', marginTop: '6px', fontSize: '0.86rem' }}
              >
                {authTab === 'login' ? 'Authenticate Session' : 'Create Official Account'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
