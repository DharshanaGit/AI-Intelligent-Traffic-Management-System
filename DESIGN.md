# DESIGN.md — AI Intelligent Traffic Management System

A dark, high-density, mission-critical operational interface inspired by Linear and Tesla telemetry design systems. Built for traffic operators, control room officers, and enforcement authorities managing urban road networks.

---

## 1. Design Principles & Aesthetic Philosophy

- **Engineered Restraint**: Every element serves an operational purpose. No decorative noise, no gaudy gradients, no distracting animations.
- **Deep Obsidian Surfaces**: `#090A0F` base canvas with layered charcoal cards (`#111522`, `#161B2A`) and hairline borders (`rgba(255, 255, 255, 0.08)`).
- **Quantum Accents**: Indigo (`#6366F1`) and Cobalt (`#4F46E5`) for primary interactions, Electric Cyan (`#06B6D4`) for live telemetry, and precise semantic indicators for signals.
- **Micro-Typographic Precision**: Inter / System Sans for ultra-legible labels and JetBrains Mono for telemetry, speeds, license plates, and cryptographic hash strings.
- **Strict Role-Gated State**: Clear visual distinction between an authenticated operational command state and a secure locked standby state.

---

## 2. Color Palette & Semantic Tokens

```css
:root {
  /* Canvas & Surfaces */
  --canvas-deep: #08090E;
  --surface-primary: #101420;
  --surface-secondary: #151A29;
  --surface-elevated: #1B2236;
  --surface-hover: #222B42;

  /* Borders & Hairlines */
  --hairline: rgba(255, 255, 255, 0.07);
  --hairline-strong: rgba(255, 255, 255, 0.14);
  --hairline-accent: rgba(99, 102, 241, 0.4);

  /* Primary Brand & Accents */
  --brand-primary: #6366F1;
  --brand-primary-hover: #4F46E5;
  --brand-glow: rgba(99, 102, 241, 0.15);
  --brand-cyan: #06B6D4;

  /* Semantic State Tokens */
  --traffic-green: #10B981;
  --traffic-green-glow: rgba(16, 185, 129, 0.35);
  --traffic-yellow: #F59E0B;
  --traffic-yellow-glow: rgba(245, 158, 11, 0.35);
  --traffic-red: #F43F5E;
  --traffic-red-glow: rgba(244, 63, 94, 0.35);

  /* Typography Colors */
  --text-primary: #F8FAFC;
  --text-secondary: #94A3B8;
  --text-muted: #64748B;
  --text-disabled: #475569;
}
```

---

## 3. Component Architecture & Blueprints

### A. Navigation & Telemetry Header
- Height: 64px, frosted glass background (`rgba(8, 9, 14, 0.85)` + 12px blur).
- Brand icon with glowing cobalt indicator.
- Real-time status pills: Live Ingest Mode, Database Sync State, Operator Session Badge.

### B. Authenticated Media & Viewport Card
- Aspect Ratio: 16:9 / 4:3 with zero visual distortion.
- Watermark HUD indicating stream origin (`LIVE_MP4`, `RTSP_CAMERA`, `WEBCAM`, `SIMULATION`).
- Unauthenticated overlay: Blurred backdrop with security icon, explicit directive (*"Authentication Required: Please Sign In or Create an Account to Operate System"*).

### C. Authentication & Registration Modal
- Width: 460px with subtle depth shadow (`0 25px 50px -12px rgba(0, 0, 0, 0.85)`).
- Segmented toggle tab: `Sign In` vs `Create Account`.
- Floating inputs with inline validation indicators (green check when valid, subtle rose alert when invalid).
- Native password reveal eye toggle icon.
- No pre-filled fake credentials.

### D. Traffic Light & Adaptive Advisory Housing
- Matte dark housing (`#0B0E17`) with inset shadow.
- Circular bulbs (56px) with dynamic outer glow rings matching signal state.
- Large countdown display in JetBrains Mono.

### E. Real-Time Telemetry & Chart Grid
- Doughnut Chart: Indian Mixed Vehicle composition (Auto-Rickshaw, Bike, Bus, Truck, Car, Pedestrian).
- Density Trend Chart: Rolling 60-second PCU curve with cyan gradient fill.
- Violation Distribution Bar Chart.
