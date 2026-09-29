---
name: Aerospace Stress Screening Console
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#c3c6d7'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#8d90a0'
  outline-variant: '#434655'
  surface-tint: '#b4c5ff'
  primary: '#b4c5ff'
  on-primary: '#002a78'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#0053db'
  secondary: '#7bd0ff'
  on-secondary: '#00354a'
  secondary-container: '#00a6e0'
  on-secondary-container: '#00374d'
  tertiary: '#ddb7ff'
  on-tertiary: '#490080'
  tertiary-container: '#943fe2'
  on-tertiary-container: '#faecff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#c4e7ff'
  secondary-fixed-dim: '#7bd0ff'
  on-secondary-fixed: '#001e2c'
  on-secondary-fixed-variant: '#004c69'
  tertiary-fixed: '#f0dbff'
  tertiary-fixed-dim: '#ddb7ff'
  on-tertiary-fixed: '#2c0051'
  on-tertiary-fixed-variant: '#6900b3'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-metric:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.02em
  headline-metric-mobile:
    fontFamily: JetBrains Mono
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 26px
    letterSpacing: -0.02em
  title-section:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-default:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: '0'
  body-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: '0'
  table-header:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.05em
  badge-label:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.02em
  code-telemetry:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 15px
    letterSpacing: '0'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system is engineered for mission-critical electronic component burn-in and Environmental Stress Screening (ESS) workstations deployed in avionics reliability labs and satellite qualification testbenches. The visual identity embodies an uncompromising dark industrial aesthetic built for high-stakes human-in-the-loop (HITL) diagnostics. It eliminates decorative fluff, soft gradients, and arbitrary rounded cards in favor of a precision instrumentation paradigm reminiscent of high-frequency digital oscilloscopes, spectrum analyzers, and automated test equipment (ATE) terminals.

The audience consists of reliability physicists, qualification engineers, and quality assurance leads who monitor hundreds of parametric telemetry streams simultaneously. The emotional response evoked must be one of absolute technical rigor, operational safety, and unyielding determinism under high cognitive load. Every pixel conveys dense functional signal: structural framing remains anchored in deep obsidian and midnight slate, while vibrant signal accents are strictly restricted to statistical anomalies, physics curves, and threshold breaches.

## Colors

The color palette is calibrated for high-contrast visibility against an unreflective, deep-space obsidian floor, engineered to reduce optical fatigue during extended screening shifts while preserving absolute semantic discipline.

- **Foundational Surfaces:** Base canvas sits at `#0b0f17`. Primary panels, modules, and diagnostic frames use `#111827`. Interactive panel hover states and secondary diagnostic tiers use `#1e293b`.
- **Structural Wireframing:** Precision boundaries and Cartesian plot frames are articulated with `#1e293b` (default hairlines) and `#334155` (active toolbars, high-priority perimeter focus).
- **Interactive & Telemetry Accents:** Primary execution actions, selection tabs, and system signals use Telemetry Blue (`#2563eb`). Real-time oscilloscope curves, active waveform trajectories, and input focus rings utilize Electric Cyan (`#38bdf8`).
- **Semantic Qualification Spectrum:**
  - **LOW / NOMINAL / PASS:** `#10b981` (tinted container: `rgba(16, 185, 129, 0.12)`, border: `rgba(16, 185, 129, 0.35)`).
  - **MEDIUM / DRIFT / MONITOR:** `#f59e0b` (tinted container: `rgba(245, 158, 11, 0.12)`, border: `rgba(245, 158, 11, 0.35)`).
  - **HIGH RISK / ANOMALOUS:** `#f97316` (tinted container: `rgba(249, 115, 22, 0.12)`, border: `rgba(249, 115, 22, 0.35)`).
  - **CRITICAL / REJECT / UPPER LIMIT:** `#ef4444` (tinted container: `rgba(239, 68, 68, 0.12)`, border: `rgba(239, 68, 68, 0.35)`).
  - **SCIENTIST OVERRIDE / AUDIT SIGNOFF:** Exclusively reserved for `#a855f7` (tinted container: `rgba(168, 85, 247, 0.12)`, border: `rgba(168, 85, 247, 0.35)`).
- **Foreground Hierarchy:** Highest-tier metrics and active titles use Crisp Signal White (`#f8fafc`). Technical metadata, axis labels, and engineering units use Diagnostic Slate (`#94a3b8`). Inactive timestamps and low-priority traces use Muted Charcoal (`#64748b`).

## Typography

The design system implements a strict dual-font discipline: **Inter** structures the interface hierarchy, navigation controls, and descriptive annotations, while **JetBrains Mono** is enforced across all quantitative measurements, hardware registers, statistical deviations, serial IDs, and physical units (`µA`, `mV`, `ns`, `eV`, `σ`).

Tabular figures (`font-variant-numeric: tabular-nums`) must be active across all monospace renderings to prevent visual vibration during live telemetry stream updates. Structural micro-labels, table column headers, and axis titles must be rendered in uppercase using `table-header` with an extended tracking of `0.05em`. Line heights adhere strictly to condensed bounding boxes (1.1–1.4 ratio), ensuring maximum information density without line collision on standard high-resolution engineering displays.

## Layout & Spacing

The workstation layout follows an uncompromising 4px modular spacing grid designed for high-density diagnostic telemetries. Layout architecture centers around a two-column command framework: a persistent left command rail fixed at 272px width, coupled to an expansive, fluid data viewport spanning full remaining width (optimized for 1920×1080 and 2560×1440 resolutions, with a hard minimum supported viewport of 1280px).

- **Grid & Modular Rhythms:** Telemetry tiles align across a 12-column sub-grid with 16px gutters (`gutter: 1rem`) and 16px external canvas margins (`margin: 1rem`).
- **Evidence Split-View:** Detailed component inspection views adhere to a 60/40 structural split: 60% dedicated to multi-channel oscilloscope traces and Arrhenius plots; 40% reserved for TabPFN inference trees, physics failure models, and human override logs.
- **Micro-Spacing Hierarchy:** Component internal padding uses compact steps—`space-sm` (8px) for buttons, compact badges, and table cells; `space-md` (12px) for card interiors and toolbar groupings; `space-lg` (16px) for major module separators.
- **Responsive Adaptations:** Below 1440px, the 4-column KPI strip drops into a 2x2 grid. Oscilloscope graphs prioritize vertical height over width, with data tables delegating secondary metrics to horizontal scrolling using high-visibility 5px slate scrollbars.

## Elevation & Depth

Visual hierarchy and spatial depth are established exclusively through tonal stacking, chromatic containment, and crisp hairlines, entirely bypassing standard diffused box-shadows.

1. **Base Ground (Level 0):** Canvas backdrop (`#0b0f17`), representing raw hardware substrate.
2. **Instrument Panels (Level 1):** Solid container fill (`#111827`) bounded by a 1px solid hairline (`#1e293b`). This tier anchors primary tables, trajectory plots, and status monitors.
3. **Elevated Scopes & Popovers (Level 2):** Flyouts, inspection drawers, and dropdown lists render with `#1e293b` fill, bounded by higher-luminance slate outlines (`#334155`).
4. **Modal Interventions (Level 3):** Mission-critical override dialogs utilize a `#111827` surface with `#334155` borders, supported by a 60% black backdrop overlay with an 8px blur to isolate critical screening decisions.
5. **Interactive Focus Illumination:** Zero drop shadows are permitted. Instead, focused inputs, active cards, and selected table records project a 1px stroke or 2px inset ring in Electric Cyan (`#38bdf8`) or Telemetry Blue (`#2563eb`), creating the optical impression of an illuminated physical instrument panel.

## Shapes

The design system enforces a compact, industrial shape language with a roundedness setting of `1` (Soft, 4px base radius). Broad radiuses and pill shapes are strictly prohibited to prevent an informal, consumer-app aesthetic.

- **Base Components:** Inputs, buttons, segmented controls, and badges use 4px corner radiuses (`rounded-sm`).
- **Structural Containers:** Primary telemetry panels, oscilloscope viewports, and modal dialogs maintain a maximum corner radius of 6px to 8px (`rounded-md` / `rounded-lg`).
- **Data Points & Node Indicators:** Waveform plot points, failure flags, and register pins utilize hard-cornered square geometries (0px radius) or precise micro-circles constrained to 4px–6px total diameter.

## Components

### Buttons & Interactive Controls
- **Geometry & Sizing:** Standard workstation height is 32px (`h-8`), with a compact 28px (`h-7`) variant for inline data table actions. Radius is 4px (`rounded-sm`).
- **Primary Trigger (Run Screening / Commit Batch):** Solid `#2563eb`, high-contrast `#ffffff` text, hovering to `#1d4ed8`. Active state triggers a 1px downward translation (`translate-y-px`).
- **Secondary / Peripheral Trigger:** Background `#1e293b`, 1px border `#334155`, text `#f8fafc`. Hover transition shifts background to `#283548`.
- **Destructive / Hard Reject:** Tinted crimson container (`rgba(239, 68, 68, 0.15)`), text `#ef4444`, border `rgba(239, 68, 68, 0.35)`.
- **Scientist Signoff Action:** Reserved exclusively for `#a855f7` fill or high-contrast purple border with white text.

### Telemetry Cards & Panels
- **Anatomy:** Background `#111827`, border 1px solid `#1e293b`, corner radius 6px.
- **Header Bar:** 32px height, border-bottom 1px solid `#1e293b`, featuring an 11px uppercase label in `#94a3b8` paired with right-aligned action tools or stream indicators.
- **KPI Metrics Displays:** Micro-header (10px uppercase `#94a3b8`), primary value set in 24px `JetBrains Mono` (`#f8fafc`), with baseline delta tags (`+0.42 µA/100h`) color-coded to statistical risk.

### High-Density Data Tables
- **Header:** Sticky top header in `#111827`, border-bottom 1px solid `#1e293b`. Text is 10px bold uppercase Inter with `0.05em` letter-spacing.
- **Rows:** Row height fixed at 32px to 36px. Left border highlight indicates selection. Background transitions to `#182234` on hover.
- **Alignment:** Component IDs and statuses align left; all numerical values, test hours, and sigma deviations align right in `JetBrains Mono`.

### Status Badges & Chips
- **Geometry:** 20px height, 6px horizontal padding, 4px corner radius.
- **Treatment:** Semi-translucent 12% background fill paired with a 35% opacity colored border and high-contrast solid text. Includes an inline 12px status icon.
- **Variants:** PASS (`#10b981`), MONITOR (`#f59e0b`), HIGH RISK (`#f97316`), REJECT (`#ef4444`), OVERRIDE (`#a855f7`).

### Oscilloscope & Degradation Plots
- **Viewport:** Canvas fill `#0b0f17`, framed with 1px `#1e293b` grid lines.
- **Traces:** Measured burn-in points mapped via solid `#38bdf8` line (2px stroke). Physics extrapolations rendered with dashed lines accompanied by a semi-transparent confidence envelope (`rgba(56, 189, 248, 0.12)`). Critical failure thresholds displayed as a solid `#ef4444` horizontal line.

### Inputs & Engineering Forms
- **Input Fields:** Height 32px, background `#0b0f17`, border 1px solid `#1e293b`, text 12px `JetBrains Mono` (`#f8fafc`). Focus state renders an Electric Cyan outer ring (`#38bdf8`) with zero offset.
- **Checkboxes & Segmented Toggles:** Checkboxes are 14×14px with 2px radius, dark `#0b0f17` background, and `#2563eb` fill when checked. Segmented selectors use contiguous 1px `#1e293b` borders with active tabs elevated to `#1e293b` and cyan indicator tabs.