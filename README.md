# AI-Powered Traffic Management & Dynamic Signal Control System

An intelligent, real-time urban traffic monitoring and dynamic signal control platform powered by OpenCV, YOLOv5, Flask, React, Chart.js, and MongoDB Atlas.

---

## 🌟 Key Features

1. **Live Video Processing & Object Detection**:
   - High-throughput vehicle detection using pre-trained **YOLOv5n** executed via **OpenCV DNN**.
   - Subsampling and frame-skipping optimizations allowing **20–30 FPS real-time processing** on standard consumer laptop CPUs.
   - Detects and tracks: **Cars**, **Buses**, **Trucks**, and **Motorcycles**.

2. **Traffic Violation Detection Engine**:
   - **Red Light Jumping**: Identifies vehicles crossing the virtual stop line while the traffic signal is RED.
   - **Wrong-Way Driving**: Evaluates centroid trajectory vectors against the allowed lane flow direction.
   - **Overspeeding**: Computes vehicle velocity between virtual distance markers.
   - **Evidence Generation**: Automatically crops the offending vehicle bounding box and stores evidence snapshots.

3. **Dynamic Adaptive Signal Controller**:
   - Calculates real-time lane density and queue lengths.
   - Dynamically scales green light duration (10s to 40s) using adaptive heuristics.
   - Supports manual operator override (Force Green, Force Red, Auto Mode).

4. **Interactive Command Dashboard**:
   - Built with **React** and **Tailwind-inspired glassmorphism design**.
   - **Chart.js** real-time visual analytics:
     - Vehicle Classification Breakdown (Doughnut chart)
     - Live Traffic Volume & Congestion Density History (Line chart)
     - Violation Categories Distribution (Bar chart)
   - Live MJPEG video stream overlay with signal state and bounding boxes.
   - Violation audit log with evidence snapshot modal viewer.

5. **Secure MongoDB Atlas Integration**:
   - MongoDB Atlas cloud storage for incident records and time-series telemetry.
   - Strict credential security via `.env` file (protected by `.gitignore`).
   - Resilient offline fallback: seamlessly buffers records locally if credentials or internet connection are pending.

---

## 🚀 Quick Start Guide

### 1. Configure MongoDB Atlas Password
Open the `.env` file in the project root:
```env
MONGO_URI=mongodb+srv://dharshanab1306_db_user:<db_password>@cluster0.b2uvuut.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
DB_NAME=traffic_management_db
```
Replace `<db_password>` with your database user password.

> **Note**: If `<db_password>` is not yet replaced, the system will run in high-speed local memory buffer mode without throwing any errors. Once you add your password, it will automatically sync to your remote MongoDB cluster.

### 2. Launch the Application
Run the root launcher script:
```powershell
python run.py
```

### 3. Open the Dashboard
Open your web browser and navigate to:
```
http://localhost:5000/
```

---

## 🛠️ Project Structure

```
AI Traffic Management/
├── .env                     # MongoDB connection string (never committed)
├── .gitignore               # Protects .env, node_modules, and evidence media
├── run.py                   # Root single-command application launcher
├── README.md                # Documentation
│
├── backend/
│   ├── app.py               # Flask REST API, MJPEG video streaming, static assets
│   ├── config.py            # Environment and filesystem configurations
│   ├── db_client.py         # MongoDB Atlas client with graceful offline fallback
│   ├── traffic_engine.py    # YOLOv5 detection, centroid tracking, rules & signal logic
│   ├── models/
│   │   └── yolov5n.onnx     # Lightweight YOLOv5n weights (~3.98 MB)
│   └── static/
│       └── violations/      # Cropped JPEG violation evidence snapshots
│
└── frontend/
    ├── package.json         # React, Chart.js, react-chartjs-2, Lucide icons
    ├── dist/                # Production-compiled single-page application
    └── src/
        ├── App.jsx          # Live control center dashboard
        ├── index.css        # Modern glassmorphism styling
        └── main.jsx         # React DOM entrypoint
```

---

## 🔒 Security Guarantee
- Credentials in `.env` are protected by `.gitignore`.
- Passwords and authentication strings are stripped from all console outputs and client-facing API responses.
