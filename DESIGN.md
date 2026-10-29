# DESIGN.md — AI Intelligent Traffic Management System
### Modern Web3 Professional Light Design System (Coinbase & Stripe Inspired)

A high-performance, institutional-grade traffic intelligence dashboard engineered with modern Web3 aesthetics. Built on a crisp pure white canvas with electric Web3 blue voltages, slate typography, hairline borders, and micro-elevation layering.

---

## 1. Aesthetic Philosophy & Visual Principles

- **Institutional Modern Web3 Clarity**: Clean, bright, and confident. The base canvas is soft white (`#F8FAFC`), and surfaces are pure white cards (`#FFFFFF`) with ultra-fine hairline dividers (`#E2E8F0`).
- **Brand Voltage — Web3 Electric Blue**: `#0052FF` (Coinbase & Ethereum brand primary) powers high-priority interactive buttons, active tab pills, and key telemetry metrics.
- **Micro-Layered Depth**: Zero decorative heavy drop-shadows. Depth is created through clean card-on-card layering, subtle 1px border strokes (`#E2E8F0`), and soft ambient micro-shadows (`box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)`).
- **Executive Typography Hierarchy**: Inter / System Sans for crystal-clear readability with high-contrast obsidian headings (`#0F172A`), balanced slate body text (`#475569`), and monospace accents (`#1E293B`) for vehicle IDs, timestamps, speed values, and SHA-256 cryptographic hashes.
- **Frictionless Operator Workflow**: Seamless entry into live telemetry with configurable environment credentials (`DEFAULT_EMAIL`, `DEFAULT_PASSWORD`), eliminating intrusive blocking overlays while maintaining strict cryptographic validation under the hood.

---

## 2. Color Tokens & Semantic Variables

```css
:root {
  /* Canvas & Backgrounds */
  --canvas-bg: #F8FAFC;
  --canvas-pure: #FFFFFF;
  --surface-card: #FFFFFF;
  --surface-subtle: #F1F5F9;
  --surface-hover: #E2E8F0;

  /* Borders & Hairlines */
  --border-light: #E2E8F0;
  --border-medium: #CBD5E1;
  --border-focus: #0052FF;
  --border-accent: rgba(0, 82, 255, 0.25);

  /* Web3 Brand Primary */
  --web3-blue: #0052FF;
  --web3-blue-hover: #0045D8;
  --web3-blue-soft: #EFF6FF;
  --web3-gradient: linear-gradient(135deg, #0052FF 0%, #3B82F6 100%);

  /* Ink & Typography */
  --text-ink: #0F172A;
  --text-body: #475569;
  --text-muted: #64748B;
  --text-subtle: #94A3B8;

  /* Semantic Traffic & Violation Indicators */
  --semantic-emerald: #059669;
  --semantic-emerald-bg: #ECFDF5;
  --semantic-emerald-border: #A7F3D0;

  --semantic-amber: #D97706;
  --semantic-amber-bg: #FFFBEB;
  --semantic-amber-border: #FDE68A;

  --semantic-crimson: #E11D48;
  --semantic-crimson-bg: #FFF1F2;
  --semantic-crimson-border: #FECDD3;

  --semantic-indigo: #4F46E5;
  --semantic-indigo-bg: #EEF2FF;
  --semantic-indigo-border: #C7D2FE;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);
  --shadow-dropdown: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
}
```

---

## 3. Component Architecture & UI Elements

### A. Navigation Bar (Top Header)
- **Background**: `#FFFFFF` with bottom border `1px solid #E2E8F0` and subtle backdrop blur.
- **Brand Title**: Obsidian `#0F172A` with Electric Blue shield icon, crisp subtitle in slate `#64748B`.
- **System Pills**:
  - Live AI Engine indicator: Soft emerald pill (`#ECFDF5`) with animated pulsing beacon.
  - Video Source selector: Soft blue pill with clean dropdown.
  - Active Session badge: Displays officer name, email, and role badge (`ADMIN` / `OPERATOR`) with instant profile modal and switch account triggers.

### B. Video Feed & Telemetry Viewport
- **Container**: Clean pure white casing (`#FFFFFF`) with rounded-2xl geometry, fine border `#CBD5E1`, and ambient shadow.
- **Live Stream Overlay**: High-contrast, sleek top/bottom HUD with semi-transparent glass badges (`background: rgba(15, 23, 42, 0.75); color: #FFFFFF`).
- **No Blocking Overlays**: Direct visual stream with full AI bounding boxes, tracking centroids, and speed vectors.

### C. Metric Telemetry Cards
- **Geometry**: White rectangular cards with soft padding (16px), rounded-xl (`12px`), and top accent stroke.
- **Numbers**: Big, bold numbers in `#0F172A` with subtle monospace styling.
- **Labels**: Uppercase 11px slate typography with letter-spacing `0.05em`.

### D. Adaptive Signal Controller
- **Visuals**: Clean white housing for North-South and East-West phases.
- **Lights**: Highly saturated physical traffic LEDs (Green `#10B981`, Amber `#F59E0B`, Red `#EF4444`) on clean recessed slate bezels.
- **Webster Algorithm Badge**: Shows live calculated cycle time ($C_{\text{opt}}$) and saturation ratio ($Y$) in crisp badges.

### E. Violations Stream & E-Challan Inspector
- **List Items**: Clean white list items with hover highlight `#F8FAFC` and hairline dividers.
- **Cryptographic Seal**: SHA-256 hash formatted in monospace `#64748B` with one-click verification modal.
- **E-Challan Modal**: Official Indian MoRTH legal styling on pure white parchment background with clean print-ready typography and blue court-admissible badge.
