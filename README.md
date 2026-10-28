# Secure, Real-World AI Traffic Management & Adaptive Signal System

An enterprise-grade urban traffic monitoring, violation detection, and adaptive signal decision-support system designed for real-world footage and Indian mixed traffic conditions (featuring Auto-Rickshaws, two-wheelers, buses, and commercial vehicles).

---

## 🌟 Architecture & Capabilities

### 1. Hardened Video Ingestion (Module 1)
- **Supported Sources**:
  - `UPLOAD`: Validated MP4/AVI/MOV video footage with binary magic bytes verification and size limits.
  - `WEBCAM`: Physical USB/UVC cameras via device index.
  - `RTSP`: Authorized IP camera streams with SSRF protection and auto-reconnection.
  - `SIMULATION`: Explicitly labeled procedural simulator isolated for offline sandboxed testing.
- **Stream Watchdog**: Real-time frozen frame detector ($\Delta \text{MSE} < 0.2$), FPS drop monitor, and stream status reporting (`HEALTHY`, `FROZEN`, `DISCONNECTED`, `SIMULATED`).

### 2. AI Vehicle Detection & Indian Traffic Harmonization (Module 2)
- **YOLOv5n ONNX via OpenCV DNN**: High FPS CPU inference with frame-skipping optimizations.
- **Indian Vehicle Classes**: Harmonized detection for **Auto-Rickshaws (3-wheelers)**, **Motorcycles/Scooters**, **Buses**, **Trucks**, **Cars**, and **Pedestrians**.
- **Kalman / Centroid Tracking**: Robust tracklet association across occlusions with persistent IDs.

### 3. Calibrated Violations, ANPR & Cryptographic Evidence (Module 3)
- **Perspective Homography**: 4-point geometric transformation converting road planes to real-world metric distances.
- **Calibrated Speed Trap**: Calculates velocity in $\text{km/h}$; disables speed penalties if calibration is unverified.
- **Red Light & Wrong-Way**: Polygonal stop-line crossing and directional lane vector analysis.
- **ANPR (Number Plate Recognition)**: High-contrast plate localization and OCR extraction with confidence scoring.
- **SHA-256 Evidence Chain of Custody**: Computes cryptographic hash of raw JPEG crop + timestamp + metadata.
- **Human-in-the-Loop Review**: Incidents are queued as `PENDING_REVIEW` until an operator approves (`VERIFIED`) or dismisses (`REJECTED`).

### 4. Adaptive Signal Decision Support (Module 4)
- **Passenger Car Units (PCU)**: Calculates Indian mixed traffic congestion (Bike = 0.5, Auto = 0.8, Car = 1.0, Bus/Truck = 2.5).
- **Webster Adaptive Timing**: Dynamically computes recommended green duration ($15\text{s} \le g \le 60\text{s}$), yellow clearance ($4\text{s}$), and all-red ($2\text{s}$).
- **Pedestrian Crossing Protection**: Dynamic pedestrian phase scheduling.
- **Safety Interlocks**: Operates strictly in **Decision-Support Advisory Mode**; direct hardware actuation is locked out.

### 5. Cybersecurity & RBAC (Module 6 & 7)
- **Role-Based Access Control**:
  - `ADMIN`: System configuration, camera calibration, full access (`admin / admin123`).
  - `OPERATOR`: Monitoring, manual signal override, violation review (`operator / op123`).
  - `AUDITOR`: Read-only compliance inspection (`auditor / audit123`).
- **Cryptographic Tokens**: HMAC-SHA256 signed session tokens with expiry.
- **Rate Limiting**: Sliding-window rate limiter per client IP.
- **Audit Trail**: Immutable audit logging of all operator actions to `backend/audit_trail.log`.
- **Database Resilience**: MongoDB Atlas with persistent local offline spooling (`offline_spool.json`) preventing data loss during network interruptions.

---

## 🚀 Quick Start Guide

### 1. Environment & Database Configuration
Configure root `.env` (credentials remain strictly protected in `.gitignore`):
```env
MONGO_URI=mongodb+srv://dharshanab1306_db_user:<db_password>@cluster0.b2uvuut.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
DB_NAME=traffic_management_db
FLASK_PORT=5000
```
*(If `<db_password>` is pending, the system runs with local offline spooling without throwing errors).*

### 2. Start the System
```powershell
python run.py
```

### 3. Access Dashboard
Navigate to: `http://localhost:5000/`

**Demo Credentials**:
- **Operator**: `operator` / `op123`
- **Admin**: `admin` / `admin123`
- **Auditor**: `auditor` / `audit123`

---

## 🧪 Automated Test Suite

Run the automated test suite covering all 8 verification vectors:
```powershell
python tests/test_traffic_system.py
```
Outputs:
```
Ran 8 tests in 0.328s - OK
```
