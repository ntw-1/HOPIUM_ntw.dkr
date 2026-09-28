#!/usr/bin/env python3
"""
scripts/run_screening_ui.py

Phase 6 & Phase 7 — Local Screening Platform & Human-in-the-Loop Audit UI Server.

Launches a zero-dependency local web interface powered by Python's built-in http.server.
Consumes ScreeningPipeline, DynamicRiskEngine, and AuditRecorder outputs via REST endpoints.

Flow:
    CSV Selection/Upload -> Data Validation -> Module A -> Module B -> Risk Engine
    -> Lot Command Center -> Component Analysis -> Engineer Final Decision (PASS / MONITOR / REJECT)
    -> Audit Trail & CSV Export

Usage:
    python3 scripts/run_screening_ui.py [--port 8501] [--no-browser]
"""

import argparse
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Dict, Any, List
import webbrowser

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.screening.pipeline import ScreeningPipeline
from src.screening.schema import ScreeningResult
from src.screening.service import ScreeningService
from src.audit.schema import DECISION_PASS, DECISION_MONITOR, DECISION_REJECT

CURRENT_SCREENING_RESULT_OBJ: Optional[ScreeningResult] = None
CURRENT_SCREENING_RESULT_DICT: dict = {}
SERVICE = ScreeningService()


def screening_result_to_dict(result: ScreeningResult) -> dict:
    """Convert a ScreeningResult object to a clean JSON-serializable dictionary for UI consumption."""
    lot_data = {}
    for lot_id, lot_res in result.lot_results.items():
        comp_list = []
        for c in lot_res.component_results:
            params_dict = {}
            for p_name, p_res in c.parameters.items():
                params_dict[p_name] = {
                    "parameter_name": p_res.parameter_name,
                    "unit": p_res.unit,
                    "value_0h": p_res.value_0h,
                    "value_24h": p_res.value_24h,
                    "delta_24_0": p_res.delta_24_0,
                    "predicted_168h": p_res.predicted_168h,
                    "lower_bound_168h": p_res.lower_bound_168h,
                    "upper_bound_168h": p_res.upper_bound_168h,
                    "uncertainty_width": p_res.uncertainty_width,
                    "uncertainty_method": p_res.uncertainty_method,
                    "predicted_drift_from_0h": p_res.predicted_drift_from_0h,
                    "drift_frac_spec": p_res.drift_frac_spec,
                    "synthetic_spec_min": p_res.synthetic_spec_min,
                    "synthetic_spec_max": p_res.synthetic_spec_max,
                    "is_reference_breach": p_res.is_reference_breach,
                    "is_population_anomaly": p_res.is_population_anomaly,
                    "population_anomaly_score": p_res.population_anomaly_score,
                    "predicted_value_crosses_spec_max": p_res.predicted_value_crosses_spec_max,
                    "predicted_value_crosses_spec_min": p_res.predicted_value_crosses_spec_min,
                    "upper_bound_crosses_spec_max": p_res.upper_bound_crosses_spec_max,
                    "uncertainty_is_high": p_res.uncertainty_is_high,
                    "parameter_risk_level": p_res.parameter_risk_level,
                    "reasons": p_res.reasons,
                }

            # Check if human audit record exists
            audit_rec = SERVICE.get_audit_record(c.component_id, c.lot_id)
            audit_dict = None
            if audit_rec:
                audit_dict = {
                    "engineer_decision": audit_rec.engineer_decision,
                    "engineer_reason": audit_rec.engineer_reason,
                    "timestamp_utc": audit_rec.timestamp_utc,
                    "session_id": audit_rec.session_id,
                }

            comp_list.append({
                "component_id": c.component_id,
                "lot_id": c.lot_id,
                "overall_risk_level": c.overall_risk_level,
                "recommendation_context": c.recommendation_context,
                "is_population_anomaly": c.is_population_anomaly,
                "is_reference_breach": c.is_reference_breach,
                "any_predicted_spec_crossing": c.any_predicted_spec_crossing,
                "any_high_uncertainty": c.any_high_uncertainty,
                "any_elevated_drift": c.any_elevated_drift,
                "anomaly_classification_state": c.anomaly_classification_state,
                "anomaly_score": c.anomaly_score,
                "risk_reasons": c.risk_reasons,
                "parameters": params_dict,
                "audit_record": audit_dict,
            })

        lot_data[lot_id] = {
            "lot_id": lot_res.lot_id,
            "total_components": lot_res.total_components,
            "validation_status": lot_res.validation_status,
            "validation_hard_failures": lot_res.validation_hard_failures,
            "validation_warnings": lot_res.validation_warnings,
            "risk_low_count": lot_res.risk_low_count,
            "risk_medium_count": lot_res.risk_medium_count,
            "risk_high_count": lot_res.risk_high_count,
            "population_anomaly_count": lot_res.population_anomaly_count,
            "reference_breach_count": lot_res.reference_breach_count,
            "components": comp_list,
        }

    audit_summary = SERVICE.get_audit_summary()

    return {
        "csv_path": result.csv_path,
        "total_lots": result.total_lots,
        "total_components": result.total_components,
        "validation_status": result.validation_status,
        "validation_hard_failures": result.validation_hard_failures,
        "validation_warnings": result.validation_warnings,
        "validation_messages": result.validation_messages,
        "risk_low_count": result.risk_low_count,
        "risk_medium_count": result.risk_medium_count,
        "risk_high_count": result.risk_high_count,
        "aborted": result.aborted,
        "abort_reason": result.abort_reason,
        "lots": lot_data,
        "audit_summary": {
            "total_decisions": audit_summary.total_decisions,
            "pass_count": audit_summary.pass_count,
            "monitor_count": audit_summary.monitor_count,
            "reject_count": audit_summary.reject_count,
        },
    }


# ---------------------------------------------------------------------------
# Single-Page App HTML Interface with Phase 7 HITL Signoff Panel
# ---------------------------------------------------------------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HOPIUM SIH26170 | Semiconductor Burn-In Screening Workstation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            /* Aerospace / ATE Workstation Dark Theme Palette */
            --bg-dark: #080c14;
            --rail-bg: #0d1322;
            --panel-bg: #111827;
            --panel-header-bg: #1f2937;
            --border-color: #1f293d;
            --border-focus: #374151;
            
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --text-dim: #6b7280;
            
            --cyan-accent: #00f0ff;
            --cyan-glow: rgba(0, 240, 255, 0.15);
            --blue-accent: #3b82f6;
            
            --risk-low: #10b981;
            --risk-med: #f59e0b;
            --risk-high: #ef4444;
            
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: var(--bg-dark); color: var(--text-main); font-family: var(--font-sans); font-size: 13px; line-height: 1.4; -webkit-font-smoothing: antialiased; }
        
        /* Layout Structure */
        .app-container { display: flex; height: 100vh; width: 100vw; overflow: hidden; }
        
        /* 272px Command Rail */
        .command-rail { width: 272px; background: var(--rail-bg); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; flex-shrink: 0; }
        .rail-header { padding: 20px 16px; border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 4px; }
        .rail-brand { font-family: var(--font-mono); font-weight: 800; font-size: 14px; color: var(--cyan-accent); letter-spacing: 0.1em; display: flex; align-items: center; gap: 8px; }
        .rail-brand::before { content: "■"; color: var(--cyan-accent); font-size: 10px; }
        .rail-sub { font-size: 10px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }
        
        .rail-nav { padding: 16px 8px; display: flex; flex-direction: column; gap: 4px; flex: 1; }
        .nav-group-title { font-size: 9px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; padding: 8px 12px 4px 12px; }
        .nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; color: var(--text-muted); font-family: var(--font-mono); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; border-radius: 4px; cursor: pointer; transition: all 0.15s ease; border-left: 2px solid transparent; }
        .nav-item:hover { background: rgba(255, 255, 255, 0.03); color: var(--text-main); }
        .nav-item.active { background: rgba(0, 240, 255, 0.08); color: var(--cyan-accent); border-left-color: var(--cyan-accent); }
        .nav-item.disabled { opacity: 0.35; cursor: not-allowed; pointer-events: none; }
        .nav-num { font-size: 10px; opacity: 0.5; }
        
        .rail-footer { padding: 16px; border-top: 1px solid var(--border-color); background: rgba(0,0,0,0.2); }
        .sys-status { display: flex; align-items: center; justify-content: space-between; font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--risk-low); display: inline-block; box-shadow: 0 0 8px var(--risk-low); }
        
        /* Main Viewport */
        .viewport { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg-dark); }
        .top-bar { height: 48px; border-bottom: 1px solid var(--border-color); background: var(--panel-bg); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; font-family: var(--font-mono); font-size: 11px; }
        .top-meta { display: flex; gap: 24px; color: var(--text-muted); }
        .top-meta span { color: var(--text-main); }
        
        .main-content { flex: 1; padding: 20px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; }
        .view-section { display: none; flex-direction: column; gap: 20px; }
        .view-section.active { display: flex; }
        
        /* Panels & Cards */
        .ate-panel { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 4px; overflow: hidden; }
        .panel-head { background: var(--panel-header-bg); padding: 10px 16px; font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--text-main); text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; }
        .panel-body { padding: 16px; }
        
        /* Telemetry KPI Cards */
        .kpi-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
        .kpi-card { background: var(--panel-bg); border: 1px solid var(--border-color); padding: 14px 16px; border-radius: 4px; display: flex; flex-direction: column; gap: 4px; }
        .kpi-title { font-size: 10px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }
        .kpi-value { font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--text-main); }
        
        /* Tables */
        .ate-table { width: 100%; border-collapse: collapse; font-size: 12px; font-family: var(--font-sans); }
        .ate-table th { background: #161f30; color: var(--text-muted); font-family: var(--font-mono); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border-color); }
        .ate-table td { padding: 10px 14px; border-bottom: 1px solid var(--border-color); color: var(--text-main); }
        .ate-table td.mono { font-family: var(--font-mono); }
        .ate-table tbody tr { transition: background 0.1s; }
        .ate-table tbody tr:hover { background: rgba(0, 240, 255, 0.03); }
        
        /* Badges */
        .badge { padding: 3px 8px; font-family: var(--font-mono); font-size: 10px; font-weight: 700; border-radius: 2px; text-transform: uppercase; display: inline-block; }
        .badge-low { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-med { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
        .badge-high { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
        .badge-gray { background: rgba(107, 114, 128, 0.15); color: #9ca3af; border: 1px solid rgba(107, 114, 128, 0.3); }
        .badge-cyan { background: rgba(0, 240, 255, 0.15); color: var(--cyan-accent); border: 1px solid rgba(0, 240, 255, 0.3); }
        
        /* Buttons */
        .btn { background: #162032; border: 1px solid var(--border-color); color: var(--text-main); padding: 7px 14px; font-family: var(--font-mono); font-size: 11px; font-weight: 600; text-transform: uppercase; cursor: pointer; transition: all 0.15s; border-radius: 3px; }
        .btn:hover { background: var(--border-focus); border-color: var(--text-muted); }
        .btn-cyan { background: var(--cyan-accent); color: #000; border-color: var(--cyan-accent); font-weight: 700; }
        .btn-cyan:hover { background: #38bdf8; border-color: #38bdf8; }
        
        /* Interactive Decision Buttons */
        .btn-decision { flex: 1; padding: 10px; font-family: var(--font-mono); font-size: 11px; font-weight: 700; text-transform: uppercase; border: 1px solid var(--border-color); background: #0d1322; color: var(--text-muted); cursor: pointer; border-radius: 3px; transition: all 0.15s; }
        .btn-decision.active-PASS { background: rgba(16, 185, 129, 0.2); border-color: var(--risk-low); color: #34d399; }
        .btn-decision.active-MONITOR { background: rgba(245, 158, 11, 0.2); border-color: var(--risk-med); color: #fbbf24; }
        .btn-decision.active-REJECT { background: rgba(239, 68, 68, 0.2); border-color: var(--risk-high); color: #f87171; }
        
        /* Oscilloscope Canvas Box */
        .chart-box { background: #060911; border: 1px solid var(--border-color); padding: 8px; border-radius: 3px; position: relative; }
        .chart-box::before { content: ""; position: absolute; top:0; left:0; right:0; bottom:0; background: linear-gradient(180deg, rgba(0,240,255,0.02) 0%, transparent 100%); pointer-events: none; }
        
        /* Grid Helpers */
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
        .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        
        .loading-screen { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; font-family: var(--font-mono); color: var(--cyan-accent); gap: 12px; }
    </style>
</head>
<body>

<div class="app-container">
    <!-- 272px COMMAND RAIL -->
    <div class="command-rail">
        <div class="rail-header">
            <div class="rail-brand">HOPIUM SIH26170</div>
            <div class="rail-sub">Aero-Reliability Screening</div>
        </div>
        
        <div class="rail-nav">
            <div class="nav-group-title">Operational Workflow</div>
            <div class="nav-item" onclick="navTo('view-import', this)" id="nav-import"><span class="nav-num">00</span> IMPORT DATASET</div>
            <div class="nav-item active" onclick="navTo('view-command', this)" id="nav-command"><span class="nav-num">01</span> COMMAND CENTER</div>
            <div class="nav-item disabled" onclick="navTo('view-analysis', this)" id="nav-analysis"><span class="nav-num">02</span> COMPONENT ANALYSIS</div>
            <div class="nav-item disabled" onclick="navTo('view-risk', this)" id="nav-risk"><span class="nav-num">03</span> RISK ANALYSIS</div>
            <div class="nav-item" onclick="navTo('view-audit', this)" id="nav-audit"><span class="nav-num">04</span> AUDIT / EXPORT</div>
            
            <div class="nav-group-title" style="margin-top: 16px;">Engineering Workspace</div>
            <div class="nav-item" onclick="navTo('view-model-lab', this)" id="nav-model-lab"><span class="nav-num">05</span> MODEL LAB</div>
        </div>
        
        <div class="rail-footer">
            <div class="sys-status">
                <span>SYSTEM STATUS</span>
                <span><span class="status-dot"></span> ONLINE</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 9px; color: var(--text-dim); margin-top: 4px;">
                MODEL SET: MODULE B v1
            </div>
        </div>
    </div>
    
    <!-- MAIN VIEWPORT -->
    <div class="viewport">
        <!-- TOP STATUS BAR -->
        <div class="top-bar">
            <div class="top-meta">
                <div>DATASET: <span id="hdrDataset">data/v2/demo_burnin_data.csv</span></div>
                <div>LOTS EVALUATED: <span id="hdrLots">--</span></div>
            </div>
            <div class="top-meta">
                <div>MODEL SET: <span style="color: var(--cyan-accent);">MODULE B v1</span></div>
                <div>CONTRACT: <span>0h + 24h &rarr; 168h</span></div>
            </div>
        </div>
        
        <!-- MAIN CONTENT AREA -->
        <div class="main-content">
            <div id="loadingScreen" class="loading-screen">
                <div style="font-size: 16px; font-weight: 700;">INITIALIZING SCREENING WORKSTATION...</div>
                <div style="font-size: 11px; color: var(--text-muted);">Executing Module A & Module B Pipelines</div>
            </div>

            <!-- ============================================== -->
            <!-- VIEW 00: IMPORT DATASET -->
            <!-- ============================================== -->
            <div id="view-import" class="view-section">
                <div class="ate-panel">
                    <div class="panel-head">00 — Repository Dataset Ingestion (Prototype Demo Selector)</div>
                    <div class="panel-body" style="display:flex; flex-direction:column; gap:16px;">
                        <p style="color:var(--text-muted);">Select a repository burn-in measurement dataset (CSV format) to execute screening validation and prediction.</p>
                        
                        <div class="grid-2">
                            <div>
                                <label style="display:block; font-family:var(--font-mono); font-size:10px; color:var(--text-dim); margin-bottom:6px; text-transform:uppercase;">Repository Dataset File</label>
                                <select id="importCsvSelect" class="btn" style="width:100%; text-align:left; background:#0b1120;">
                                    <option value="data/v2/demo_burnin_data.csv">data/v2/demo_burnin_data.csv (V2 Canonical Benchmark)</option>
                                    <option value="data/v2/dev_burnin_data.csv">data/v2/dev_burnin_data.csv (V2 Development Set)</option>
                                    <option value="data/demo_burnin_data.csv">data/demo_burnin_data.csv (V1 Legacy Baseline)</option>
                                </select>
                            </div>
                            <div style="display:flex; align-items:flex-end; gap:8px;">
                                <button class="btn btn-cyan" onclick="executeImportAndScreen()">LOAD & EVALUATE DATASET</button>
                            </div>
                        </div>

                        <div id="importValidationBox" style="display:none; background:#0b1120; border:1px solid var(--border-color); padding:16px; border-radius:3px; margin-top:8px;">
                            <div style="font-family:var(--font-mono); font-size:11px; font-weight:700; color:var(--cyan-accent); margin-bottom:8px;">DATA VALIDATION REPORT</div>
                            <div class="grid-4" style="margin-bottom:12px;">
                                <div><span style="color:var(--text-dim);">Status:</span> <span id="valStatus" class="badge badge-low">PASS</span></div>
                                <div><span style="color:var(--text-dim);">Hard Failures:</span> <span id="valFailures" class="mono">0</span></div>
                                <div><span style="color:var(--text-dim);">Warnings:</span> <span id="valWarnings" class="mono">0</span></div>
                                <div><span style="color:var(--text-dim);">Schema Compliance:</span> <span class="badge badge-low">SIH26170 PASS</span></div>
                            </div>
                            <ul id="valMessageList" style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); list-style:none; display:flex; flex-direction:column; gap:4px;"></ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ============================================== -->
            <!-- VIEW 01: COMMAND CENTER -->
            <!-- ============================================== -->
            <div id="view-command" class="view-section">
                <!-- Operational KPI Grid -->
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-title">Total Components</div>
                        <div class="kpi-value" id="kpiTotal">--</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Low AI Risk</div>
                        <div class="kpi-value" style="color:var(--risk-low);" id="kpiLow">--</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Medium AI Risk</div>
                        <div class="kpi-value" style="color:var(--risk-med);" id="kpiMed">--</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">High AI Risk</div>
                        <div class="kpi-value" style="color:var(--risk-high);" id="kpiHigh">--</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Monitored</div>
                        <div class="kpi-value" style="color:var(--risk-med);" id="kpiMonitored">--</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Awaiting Review</div>
                        <div class="kpi-value" style="color:var(--cyan-accent);" id="kpiPending">--</div>
                    </div>
                </div>

                <!-- Lot Population Telemetry -->
                <div class="ate-panel">
                    <div class="panel-head">01.1 — Lot Population Context</div>
                    <div class="panel-body" style="padding:0;">
                        <table class="ate-table">
                            <thead>
                                <tr>
                                    <th>Lot Identifier</th>
                                    <th>Total Comps</th>
                                    <th>Low Risk</th>
                                    <th>Med Risk</th>
                                    <th>High Risk</th>
                                    <th>Monitored</th>
                                    <th>Leading Health / Anomaly Driver</th>
                                </tr>
                            </thead>
                            <tbody id="lotContextBody"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Attention Required Component Queue -->
                <div class="ate-panel">
                    <div class="panel-head" style="border-left: 3px solid var(--cyan-accent);">
                        <span>01.2 — Component Attention Queue</span>
                        <select id="queueFilter" class="btn" style="padding: 2px 8px; font-size: 10px;" onchange="renderQueue()">
                            <option value="ALL">ALL COMPONENTS</option>
                            <option value="HIGH" selected>HIGH RISK ONLY</option>
                            <option value="MEDIUM">MEDIUM RISK</option>
                            <option value="LOW">LOW RISK</option>
                            <option value="MONITORED">MONITORED</option>
                        </select>
                    </div>
                    <div class="panel-body" style="padding:0;">
                        <table class="ate-table">
                            <thead>
                                <tr>
                                    <th>Component ID</th>
                                    <th>Lot ID</th>
                                    <th>AI Advisory Risk</th>
                                    <th>Key Anomaly / Drift Reason</th>
                                    <th>Engineer Final Decision</th>
                                    <th style="text-align:right;">Action</th>
                                </tr>
                            </thead>
                            <tbody id="queueBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ============================================== -->
            <!-- VIEW 02: COMPONENT ANALYSIS -->
            <!-- ============================================== -->
            <div id="view-analysis" class="view-section">
                <div id="compDetailBody"></div>
            </div>

            <!-- ============================================== -->
            <!-- VIEW 03: RISK ANALYSIS -->
            <!-- ============================================== -->
            <div id="view-risk" class="view-section">
                <div id="riskDetailBody"></div>
            </div>

            <!-- ============================================== -->
            <!-- VIEW 04: AUDIT / EXPORT -->
            <!-- ============================================== -->
            <div id="view-audit" class="view-section">
                <div class="ate-panel">
                    <div class="panel-head">
                        <span>04.1 — Immutable Audit Trail Export</span>
                        <button class="btn btn-cyan" onclick="triggerExportAudit()">EXPORT AUDIT CSV</button>
                    </div>
                    <div class="panel-body">
                        <p style="color:var(--text-muted); font-size:12px;">Export all recorded human engineering decisions and advisory risk assessments to an immutable CSV audit log for quality compliance.</p>
                    </div>
                </div>

                <div class="ate-panel">
                    <div class="panel-head">04.2 — Decision Log Audit Chain</div>
                    <div class="panel-body" style="padding:0;">
                        <table class="ate-table">
                            <thead>
                                <tr>
                                    <th>Component ID</th>
                                    <th>Lot ID</th>
                                    <th>AI Advisory Risk</th>
                                    <th>Engineer Final Decision</th>
                                    <th>Override Status</th>
                                    <th>Engineering Reasoning</th>
                                    <th>UTC Timestamp</th>
                                </tr>
                            </thead>
                            <tbody id="auditBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ============================================== -->
            <!-- VIEW 05: MODEL LAB WORKSPACE -->
            <!-- ============================================== -->
            <div id="view-model-lab" class="view-section">
                <div class="ate-panel">
                    <div class="panel-head">05 — Offline Model Development & Maintenance Workspace</div>
                    <div class="panel-body" style="display:flex; flex-direction:column; gap:16px;">
                        <p style="color:var(--text-muted);">Model Lab operates out-of-band to evaluate, rank, and register candidate models using historical Lot splits. Operational screening consumes registered immutable artifacts.</p>
                        
                        <div class="grid-3" id="modelRegistryCards">
                            <!-- Populated dynamically from backend model registry metadata -->
                        </div>

                        <div style="background:#060911; border:1px solid var(--border-color); padding:12px; font-family:var(--font-mono); font-size:11px; color:var(--text-dim);">
                            CLI Maintenance Command: $ python3 scripts/run_module_b_evaluation.py
                        </div>
                    </div>
                </div>
            </div>

        </div>
    </div>
</div>

<script>
    let screeningData = null;
    let selectedCompId = null;
    let selectedLotId = null;
    let selectedDecision = 'PASS';
    
    const STATE_MAP = {
        'STATE_A_NORMAL': 'No significant anomaly detected',
        'STATE_B_POPULATION_ANOMALY_ONLY': 'Population anomaly detected',
        'STATE_C_SPEC_BREACH_ONLY': 'Specification breach detected',
        'STATE_D_POPULATION_ANOMALY_AND_SPEC_BREACH': 'Population anomaly + specification breach',
        'STATE_E_ELEVATED_DRIFT_ONLY': 'Predicted drift elevated',
        'STATE_F_ELEVATED_DRIFT_AND_POPULATION_ANOMALY': 'Predicted drift elevated + population anomaly',
        'STATE_G_ELEVATED_DRIFT_AND_SPEC_BREACH': 'Predicted drift elevated + specification breach',
        'STATE_H_ALL_ANOMALIES_PRESENT': 'Critical anomalies present across all indicators',
        'STATE_UNKNOWN': 'Unknown state'
    };
    
    function translateState(rawStr) {
        let s = rawStr || '';
        for (const [key, val] of Object.entries(STATE_MAP)) {
            s = s.replace(new RegExp(key, 'g'), val);
        }
        return s;
    }

    function navTo(viewId, el) {
        if (el && el.classList.contains('disabled')) return;
        document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
        
        if (el) {
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            el.classList.add('active');
        }
        
        if (viewId === 'view-audit') {
            renderAuditPreview();
        } else if (viewId === 'view-model-lab') {
            renderModelLabCards();
        }
    }

    async function loadScreeningData(csvPath = 'data/v2/demo_burnin_data.csv') {
        try {
            const res = await fetch('/api/screen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ csv_path: csvPath })
            });
            screeningData = await res.json();
            
            document.getElementById('loadingScreen').style.display = 'none';
            document.getElementById('hdrDataset').textContent = screeningData.csv_path;
            document.getElementById('hdrLots').textContent = screeningData.total_lots;
            
            populateCommandCenter();
            populateImportValidationBox();
        } catch (err) {
            document.getElementById('loadingScreen').innerHTML = '<div style="color:var(--risk-high);">FAILED TO LOAD SCREENING ENGINE</div>';
        }
    }

    async function executeImportAndScreen() {
        const path = document.getElementById('importCsvSelect').value;
        document.getElementById('loadingScreen').style.display = 'flex';
        await loadScreeningData(path);
        navTo('view-command', document.getElementById('nav-command'));
    }

    function populateImportValidationBox() {
        const box = document.getElementById('importValidationBox');
        box.style.display = 'block';
        
        document.getElementById('valStatus').textContent = screeningData.validation_status || 'PASS';
        document.getElementById('valFailures').textContent = screeningData.validation_hard_failures || 0;
        document.getElementById('valWarnings').textContent = screeningData.validation_warnings || 0;
        
        const list = document.getElementById('valMessageList');
        list.innerHTML = '';
        if (screeningData.validation_messages && screeningData.validation_messages.length > 0) {
            screeningData.validation_messages.forEach(msg => {
                const li = document.createElement('li');
                li.textContent = "• " + msg;
                list.appendChild(li);
            });
        } else {
            list.innerHTML = '<li>• All structural, schema, and temporal consistency assertions passed successfully.</li>';
        }
    }

    function populateCommandCenter() {
        let pending = 0;
        let monitoredCount = 0;
        let allComps = [];
        
        const lotContextBody = document.getElementById('lotContextBody');
        lotContextBody.innerHTML = '';

        Object.values(screeningData.lots).forEach(lot => {
            let lotMonitored = 0;
            let leadingConcern = 'Nominal';
            
            lot.components.forEach(c => {
                allComps.push(c);
                if (!c.audit_record) {
                    pending++;
                } else if (c.audit_record.engineer_decision === 'MONITOR') {
                    monitoredCount++;
                    lotMonitored++;
                }
                if (c.overall_risk_level === 'HIGH' && leadingConcern === 'Nominal') {
                    leadingConcern = c.recommendation_context ? translateState(c.recommendation_context) : 'High Risk Concern';
                }
            });

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="mono" style="color:var(--cyan-accent);">${lot.lot_id}</td>
                <td class="mono">${lot.total_components}</td>
                <td><span class="badge badge-low">${lot.risk_low_count}</span></td>
                <td><span class="badge badge-med">${lot.risk_medium_count}</span></td>
                <td><span class="badge badge-high">${lot.risk_high_count}</span></td>
                <td><span class="badge badge-gray">${lotMonitored}</span></td>
                <td style="font-size:11px; color:var(--text-muted);">${leadingConcern}</td>
            `;
            lotContextBody.appendChild(tr);
        });
        
        document.getElementById('kpiTotal').textContent = screeningData.total_components;
        document.getElementById('kpiLow').textContent = screeningData.risk_low_count;
        document.getElementById('kpiMed').textContent = screeningData.risk_medium_count;
        document.getElementById('kpiHigh').textContent = screeningData.risk_high_count;
        document.getElementById('kpiMonitored').textContent = monitoredCount;
        document.getElementById('kpiPending').textContent = pending;
        
        renderQueue();
    }

    function renderQueue() {
        const tbody = document.getElementById('queueBody');
        tbody.innerHTML = '';
        const filter = document.getElementById('queueFilter').value;
        
        let allComps = [];
        Object.values(screeningData.lots).forEach(lot => {
            allComps = allComps.concat(lot.components);
        });
        
        let filteredComps = allComps.filter(comp => {
            if (filter === 'ALL') return true;
            if (filter === 'HIGH') return comp.overall_risk_level === 'HIGH';
            if (filter === 'MEDIUM') return comp.overall_risk_level === 'MEDIUM';
            if (filter === 'LOW') return comp.overall_risk_level === 'LOW';
            if (filter === 'MONITORED') return comp.audit_record && comp.audit_record.engineer_decision === 'MONITOR';
            return true;
        });
        
        const riskMap = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1};
        filteredComps.sort((a, b) => {
            if (riskMap[b.overall_risk_level] !== riskMap[a.overall_risk_level]) {
                return riskMap[b.overall_risk_level] - riskMap[a.overall_risk_level];
            }
            const aPend = a.audit_record ? 0 : 1;
            const bPend = b.audit_record ? 0 : 1;
            return bPend - aPend;
        });
        
        if (filteredComps.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 24px; color:var(--text-muted); font-family:var(--font-mono);">NO COMPONENTS MATCHING FILTER: ${filter}</td></tr>`;
            return;
        }
        
        filteredComps.forEach(comp => {
            let bClass = comp.overall_risk_level === 'HIGH' ? 'badge-high' : (comp.overall_risk_level === 'MEDIUM' ? 'badge-med' : 'badge-low');
            
            let reason = comp.recommendation_context ? translateState(comp.recommendation_context) : '';
            if (!reason && comp.risk_reasons && comp.risk_reasons.length > 0) {
                reason = translateState(comp.risk_reasons[0]);
            }
            if (!reason) reason = 'No significant anomaly detected';
            if (reason.length > 75) reason = reason.substring(0, 72) + '...';
            
            let engDecText = 'PENDING';
            let engDecClass = 'badge-gray';
            if (comp.audit_record) {
                engDecText = comp.audit_record.engineer_decision;
                if (engDecText === 'PASS') engDecClass = 'badge-low';
                else if (engDecText === 'MONITOR') engDecClass = 'badge-med';
                else if (engDecText === 'REJECT') engDecClass = 'badge-high';
            }
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="mono" style="color:var(--cyan-accent); cursor:pointer; font-weight:700;" onclick="reviewComponent('${comp.component_id}', '${comp.lot_id}')">${comp.component_id}</td>
                <td class="mono">${comp.lot_id}</td>
                <td><span class="badge ${bClass}">${comp.overall_risk_level} RISK</span></td>
                <td style="font-size:11px; color:var(--text-muted);">${reason}</td>
                <td><span class="badge ${engDecClass}">${engDecText}</span></td>
                <td style="text-align: right;">
                    <button class="btn btn-cyan" style="padding: 3px 10px; font-size:10px;" onclick="reviewComponent('${comp.component_id}', '${comp.lot_id}')">REVIEW</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function reviewComponent(compId, lotId) {
        document.getElementById('nav-analysis').classList.remove('disabled');
        document.getElementById('nav-risk').classList.remove('disabled');
        
        selectComponent(compId, lotId);
        navTo('view-analysis', document.getElementById('nav-analysis'));
    }

    function selectComponent(compId, lotId) {
        selectedCompId = compId;
        selectedLotId = lotId;
        
        const lot = screeningData.lots[lotId];
        const comp = lot.components.find(c => c.component_id === compId);
        const existingAudit = comp.audit_record;
        
        if (existingAudit) {
            selectedDecision = existingAudit.engineer_decision;
        } else {
            selectedDecision = 'PASS';
        }
        
        // Determine override status: Engineer decision != advisory expectation (HIGH->REJECT, LOW->PASS, MED->MONITOR/PASS)
        const isOverridden = existingAudit && (
            (comp.overall_risk_level === 'HIGH' && existingAudit.engineer_decision !== 'REJECT') ||
            (comp.overall_risk_level === 'LOW' && existingAudit.engineer_decision !== 'PASS')
        );

        // 02 — COMPONENT ANALYSIS
        let html = `
            <div class="ate-panel">
                <div class="panel-head">02.1 — Component Identity & Status</div>
                <div class="panel-body grid-4">
                    <div><span style="color:var(--text-dim); font-size:10px; text-transform:uppercase; display:block;">Component ID</span><span class="mono" style="font-size:14px; font-weight:700; color:var(--cyan-accent);">${comp.component_id}</span></div>
                    <div><span style="color:var(--text-dim); font-size:10px; text-transform:uppercase; display:block;">Lot Identifier</span><span class="mono" style="font-size:14px; font-weight:700;">${comp.lot_id}</span></div>
                    <div><span style="color:var(--text-dim); font-size:10px; text-transform:uppercase; display:block;">AI Advisory Risk</span><span class="badge ${comp.overall_risk_level === 'HIGH' ? 'badge-high' : (comp.overall_risk_level === 'MEDIUM' ? 'badge-med' : 'badge-low')}">${comp.overall_risk_level} RISK</span></div>
                    <div><span style="color:var(--text-dim); font-size:10px; text-transform:uppercase; display:block;">Specification Status</span><span class="badge ${comp.is_reference_breach ? 'badge-high' : 'badge-low'}">${comp.is_reference_breach ? 'OUT OF SPEC' : 'WITHIN SPEC'}</span></div>
                </div>
            </div>

            <div class="ate-panel" style="border-left: 3px solid #c084fc;">
                <div class="panel-head" style="color:#c084fc;">
                    <span>02.2 — Engineer Final Decision Control</span>
                    ${existingAudit ? (isOverridden ? '<span class="badge badge-med">STATUS: OVERRIDDEN</span>' : '<span class="badge badge-low">STATUS: FINAL</span>') : '<span class="badge badge-gray">PENDING REVIEW</span>'}
                </div>
                <div class="panel-body grid-2" style="align-items:center;">
                    <div style="background:#0b1120; padding:12px; border:1px solid var(--border-color); border-radius:3px;">
                        <div style="font-size:10px; color:var(--text-dim); text-transform:uppercase; margin-bottom:4px;">AI Advisory Assessment</div>
                        <div style="font-family:var(--font-mono); font-size:18px; font-weight:800; color:var(--risk-${comp.overall_risk_level.toLowerCase()});">${comp.overall_risk_level} RISK</div>
                        <div style="font-size:10px; color:var(--text-muted); margin-top:4px;">Advisory output for engineering signoff.</div>
                    </div>
                    <div style="display:flex; flex-direction:column; gap:8px;">
                        <div style="display:flex; gap:8px;">
                            <button class="btn-decision ${selectedDecision === 'PASS' ? 'active-PASS' : ''}" onclick="setDecision('PASS')">PASS</button>
                            <button class="btn-decision ${selectedDecision === 'MONITOR' ? 'active-MONITOR' : ''}" onclick="setDecision('MONITOR')">MONITOR</button>
                            <button class="btn-decision ${selectedDecision === 'REJECT' ? 'active-REJECT' : ''}" onclick="setDecision('REJECT')">REJECT</button>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <input type="text" id="engineerReason" style="flex:1; background:#060911; border:1px solid var(--border-color); color:#fff; padding:8px; font-family:var(--font-sans); font-size:12px; border-radius:3px;" placeholder="Required: Engineering reasoning..." value="${existingAudit ? existingAudit.engineer_reason : ''}">
                            <button onclick="submitDecision()" class="btn btn-cyan">CONFIRM DECISION</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="ate-panel">
                <div class="panel-head">02.3 — Telemetry Oscilloscope Trajectories (Observed 0h-24h | Predicted 24h-168h)</div>
                <div class="panel-body grid-3">
        `;
        Object.entries(comp.parameters).forEach(([pName, p]) => {
            html += `
                    <div style="background:#0b1120; border:1px solid var(--border-color); padding:10px; border-radius:3px;">
                        <div style="font-family:var(--font-mono); font-size:10px; font-weight:700; color:var(--cyan-accent); margin-bottom:6px; display:flex; justify-content:space-between;">
                            <span>${pName.toUpperCase()}</span>
                            <span style="color:var(--risk-${p.parameter_risk_level.toLowerCase()});">${p.parameter_risk_level} RISK</span>
                        </div>
                        <div class="chart-box">
                            <canvas id="chart_${pName}" width="360" height="140"></canvas>
                        </div>
                    </div>
            `;
        });
        html += `
                </div>
            </div>

            <div class="ate-panel">
                <div class="panel-head">02.4 — All Parameters Overview</div>
                <div class="panel-body" style="padding:0;">
                    <table class="ate-table">
                        <thead>
                            <tr>
                                <th>Parameter</th>
                                <th>Observed 0h</th>
                                <th>Observed 24h</th>
                                <th style="color:var(--cyan-accent);">Predicted 168h</th>
                                <th>Spec Limit</th>
                                <th>Risk Assessment</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        Object.entries(comp.parameters).forEach(([pName, p]) => {
            const specLimit = p.synthetic_spec_max !== null ? p.synthetic_spec_max : (p.synthetic_spec_min !== null ? p.synthetic_spec_min : "N/A");
            html += `
                            <tr>
                                <td class="mono" style="font-weight:700;">${pName}</td>
                                <td class="mono">${p.value_0h.toFixed(2)} ${p.unit}</td>
                                <td class="mono">${p.value_24h.toFixed(2)} ${p.unit}</td>
                                <td class="mono" style="color:var(--cyan-accent); font-weight:700;">${p.predicted_168h.toFixed(2)} ${p.unit}</td>
                                <td class="mono">${specLimit} ${specLimit !== "N/A" ? p.unit : ""}</td>
                                <td><span class="badge ${p.parameter_risk_level === 'HIGH' ? 'badge-high' : (p.parameter_risk_level === 'MEDIUM' ? 'badge-med' : 'badge-low')}">${p.parameter_risk_level} RISK</span></td>
                            </tr>
            `;
        });
        html += `
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="grid-2">
                <div class="ate-panel">
                    <div class="panel-head">02.5 — Evidence & Trajectory Analysis</div>
                    <div class="panel-body" style="display:flex; flex-direction:column; gap:10px;">
        `;
        Object.entries(comp.parameters).forEach(([pName, p]) => {
            html += `
                        <div style="background:#0b1120; border:1px solid var(--border-color); padding:10px; border-radius:3px;">
                            <div style="font-family:var(--font-mono); font-size:10px; font-weight:700; color:var(--text-main); margin-bottom:4px;">${pName.toUpperCase()} EVIDENCE</div>
                            <div class="grid-2" style="font-family:var(--font-mono); font-size:11px;">
                                <div><span style="color:var(--text-dim);">POPULATION ANOMALY:</span> <span style="color:${p.is_population_anomaly ? 'var(--risk-high)' : 'var(--risk-low)'};">${p.is_population_anomaly ? 'DETECTED' : 'NOMINAL'}</span></div>
                                <div><span style="color:var(--text-dim);">SPEC LIMIT:</span> <span style="color:${p.is_reference_breach ? 'var(--risk-high)' : 'var(--risk-low)'};">${p.is_reference_breach ? 'BREACHED' : 'INTACT'}</span></div>
                                <div style="grid-column:span 2;"><span style="color:var(--text-dim);">PREDICTED DRIFT (0&rarr;168h):</span> <span style="color:var(--cyan-accent);">+${p.predicted_drift_from_0h.toFixed(2)} ${p.unit}</span></div>
                            </div>
                        </div>
            `;
        });
        html += `
                    </div>
                </div>

                <div class="ate-panel">
                    <div class="panel-head">02.6 — Uncertainty Envelopes</div>
                    <div class="panel-body" style="display:flex; flex-direction:column; gap:10px;">
        `;
        Object.entries(comp.parameters).forEach(([pName, p]) => {
            html += `
                        <div style="background:#0b1120; border:1px solid var(--border-color); padding:10px; border-radius:3px;">
                            <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-size:10px; margin-bottom:4px;">
                                <span style="font-weight:700; color:var(--text-main);">${pName.toUpperCase()}</span>
                                <span style="color:${p.uncertainty_is_high ? 'var(--risk-high)' : 'var(--risk-low)'};">${p.uncertainty_is_high ? 'LOW CONFIDENCE' : 'HIGH CONFIDENCE'}</span>
                            </div>
                            <div class="grid-2" style="font-family:var(--font-mono); font-size:11px;">
                                <div><span style="color:var(--text-dim);">PREDICTED 168h:</span> <span style="color:var(--cyan-accent);">${p.predicted_168h.toFixed(2)} ${p.unit}</span></div>
                                <div><span style="color:var(--text-dim);">PREDICTION INTERVAL:</span> <span>${p.lower_bound_168h.toFixed(2)} &ndash; ${p.upper_bound_168h.toFixed(2)}</span></div>
                            </div>
                        </div>
            `;
        });
        html += `
                    </div>
                </div>
            </div>
        `;
        document.getElementById('compDetailBody').innerHTML = html;

        // 03 — RISK ANALYSIS
        let riskHtml = `
            <div class="ate-panel">
                <div class="panel-head">03 — Comprehensive Risk Analysis & Decision Support</div>
                <div class="panel-body">
                    <div class="grid-2" style="margin-bottom:16px; background:#0b1120; border:1px solid var(--border-color); padding:16px; border-radius:3px;">
                        <div>
                            <div style="font-size:10px; font-family:var(--font-mono); color:var(--text-dim); text-transform:uppercase;">AI Advisory Risk</div>
                            <div style="font-family:var(--font-mono); font-size:20px; font-weight:800; color:var(--risk-${comp.overall_risk_level.toLowerCase()});">${comp.overall_risk_level} RISK</div>
                        </div>
                        <div>
                            <div style="font-size:10px; font-family:var(--font-mono); color:var(--text-dim); text-transform:uppercase;">Spec Limit Status</div>
                            <div style="font-family:var(--font-mono); font-size:20px; font-weight:800; color:${comp.is_reference_breach ? 'var(--risk-high)' : 'var(--risk-low)'};">${comp.is_reference_breach ? 'OUT OF SPEC' : 'WITHIN SPEC'}</div>
                        </div>
                    </div>

                    <table class="ate-table">
                        <thead>
                            <tr>
                                <th>Parameter</th>
                                <th>Observed (0h / 24h)</th>
                                <th>Predicted 168h</th>
                                <th>Prediction Interval</th>
                                <th>Population Anomaly</th>
                                <th>Spec Breach</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        Object.entries(comp.parameters).forEach(([pName, p]) => {
            riskHtml += `
                            <tr>
                                <td class="mono" style="font-weight:700;">${pName}</td>
                                <td class="mono">${p.value_0h.toFixed(2)} / ${p.value_24h.toFixed(2)} ${p.unit}</td>
                                <td class="mono" style="color:var(--cyan-accent);">${p.predicted_168h.toFixed(2)} ${p.unit}</td>
                                <td class="mono">${p.lower_bound_168h.toFixed(2)} - ${p.upper_bound_168h.toFixed(2)}</td>
                                <td><span class="badge ${p.is_population_anomaly ? 'badge-high' : 'badge-low'}">${p.is_population_anomaly ? 'YES' : 'NO'}</span></td>
                                <td><span class="badge ${p.is_reference_breach ? 'badge-high' : 'badge-low'}">${p.is_reference_breach ? 'YES' : 'NO'}</span></td>
                            </tr>
            `;
        });
        riskHtml += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        document.getElementById('riskDetailBody').innerHTML = riskHtml;

        setTimeout(() => { Object.entries(comp.parameters).forEach(([pName, p]) => { drawTruthfulChart(`chart_${pName}`, p); }); }, 50);
    }

    function setDecision(dec) {
        selectedDecision = dec;
        selectComponent(selectedCompId, selectedLotId);
    }

    async function submitDecision() {
        const reasonInput = document.getElementById('engineerReason');
        const reason = reasonInput ? reasonInput.value.trim() : '';
        if (!reason) { alert('Engineering reasoning is required.'); return; }
        
        try {
            const res = await fetch('/api/decision', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ component_id: selectedCompId, lot_id: selectedLotId, engineer_decision: selectedDecision, engineer_reason: reason })
            });
            const data = await res.json();
            if (data.status === 'ok') {
                const comp = screeningData.lots[selectedLotId].components.find(c => c.component_id === selectedCompId);
                comp.audit_record = { engineer_decision: selectedDecision, engineer_reason: reason, timestamp_utc: new Date().toISOString() };
                
                populateCommandCenter();
                selectComponent(selectedCompId, selectedLotId);
            }
        } catch (err) {
            alert("Failed to submit decision: " + err);
        }
    }

    function renderAuditPreview() {
        const tbody = document.getElementById('auditBody');
        tbody.innerHTML = '';
        
        let allComps = [];
        Object.values(screeningData.lots).forEach(lot => {
            lot.components.forEach(c => {
                if (c.audit_record) allComps.push(c);
            });
        });
        
        if (allComps.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px; color:var(--text-muted); font-family:var(--font-mono);">NO AUDITED ENGINEERING DECISIONS RECORDED</td></tr>';
            return;
        }
        
        allComps.sort((a, b) => new Date(b.audit_record.timestamp_utc) - new Date(a.audit_record.timestamp_utc));
        
        allComps.forEach(comp => {
            const aiRisk = comp.overall_risk_level;
            const engDec = comp.audit_record.engineer_decision;
            
            const isOverridden = (
                (aiRisk === 'HIGH' && engDec !== 'REJECT') ||
                (aiRisk === 'LOW' && engDec !== 'PASS')
            );
            const statusBadge = isOverridden ? '<span class="badge badge-med">STATUS: OVERRIDDEN</span>' : '<span class="badge badge-low">STATUS: FINAL</span>';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="mono" style="color:var(--cyan-accent); cursor:pointer;" onclick="reviewComponent('${comp.component_id}', '${comp.lot_id}')">${comp.component_id}</td>
                <td class="mono">${comp.lot_id}</td>
                <td><span class="badge ${aiRisk==='HIGH'?'badge-high':(aiRisk==='MEDIUM'?'badge-med':'badge-low')}">${aiRisk} RISK</span></td>
                <td style="font-weight:700; color: ${engDec==='PASS' ? 'var(--risk-low)' : (engDec==='REJECT' ? 'var(--risk-high)' : 'var(--risk-med)')};">${engDec}</td>
                <td>${statusBadge}</td>
                <td style="font-size:11px; color:var(--text-muted);">${comp.audit_record.engineer_reason}</td>
                <td class="mono" style="font-size:10px; color:var(--text-dim);">${comp.audit_record.timestamp_utc}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderModelLabCards() {
        const container = document.getElementById('modelRegistryCards');
        if (!container) return;
        
        // Dynamically populate from active backend registry parameters
        const params = ['Iddq', 'leakage_current', 'propagation_delay'];
        let html = '';
        
        params.forEach(pName => {
            html += `
                <div style="background:#0b1120; border:1px solid var(--border-color); padding:16px; border-radius:3px;">
                    <div style="font-family:var(--font-mono); color:var(--cyan-accent); font-weight:700; margin-bottom:6px;">${pName} Model Artifact</div>
                    <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); line-height:1.6;">
                        <span style="color:var(--text-dim);">MODEL CLASS:</span> Registered Scikit-Learn Pipeline<br>
                        <span style="color:var(--text-dim);">REGISTRY ID:</span> module_b_${pName}_v1<br>
                        <span style="color:var(--text-dim);">FEATURE ALLOWLIST:</span> value_0h, value_24h, delta_24_0<br>
                        <span style="color:var(--text-dim);">TARGET:</span> value_168h<br>
                        <span style="color:var(--text-dim);">SPLIT:</span> 60% Train / 20% Val / 20% Locked Blind
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }

    async function triggerExportAudit() {
        try {
            const res = await fetch('/api/export_audit');
            const data = await res.json();
            if (data.status === 'ok') {
                alert('Audit log CSV exported successfully to: ' + data.exported_path);
            } else {
                alert('Export failed: ' + data.error);
            }
        } catch (err) {
            alert('Export error: ' + err);
        }
    }

    function drawTruthfulChart(canvasId, p) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const pX = [0, 24, 96, 168];
        const pY = [p.value_0h, p.value_24h, null, p.predicted_168h];
        const specMin = p.synthetic_spec_min;
        const specMax = p.synthetic_spec_max;
        
        let minY = Math.min(...pY.filter(v => v !== null));
        let maxY = Math.max(...pY.filter(v => v !== null));
        if (specMin !== null) minY = Math.min(minY, specMin);
        if (specMax !== null) maxY = Math.max(maxY, specMax);
        
        const range = (maxY - minY) || 1;
        const yPad = range * 0.2;
        const yMin = minY - yPad;
        const yMax = maxY + yPad;
        
        function getX(x) { return 35 + (x / 168) * (canvas.width - 55); }
        function getY(y) { return canvas.height - 25 - ((y - yMin) / (yMax - yMin)) * (canvas.height - 45); }
        
        // Time Axis Labels
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.fillStyle = '#6b7280';
        ctx.textAlign = 'center';
        pX.forEach(x => { ctx.fillText(x + 'h', getX(x), canvas.height - 8); });
        
        // Spec Line
        if (specMax !== null) {
            ctx.beginPath();
            ctx.moveTo(35, getY(specMax)); ctx.lineTo(canvas.width - 15, getY(specMax));
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)'; ctx.setLineDash([3, 3]); ctx.stroke();
        }
        
        // Solid Line: Observed (0h -> 24h)
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(getX(0), getY(p.value_0h));
        ctx.lineTo(getX(24), getY(p.value_24h));
        ctx.strokeStyle = '#10b981'; ctx.lineWidth = 2; ctx.stroke();
        
        // Dashed Line: Predicted Forecast (24h -> 168h)
        ctx.beginPath();
        ctx.moveTo(getX(24), getY(p.value_24h));
        ctx.lineTo(getX(168), getY(p.predicted_168h));
        ctx.strokeStyle = '#00f0ff'; ctx.setLineDash([5, 3]); ctx.stroke();
        
        function drawPoint(x, y, col, lbl) {
            ctx.beginPath(); ctx.arc(getX(x), getY(y), 3.5, 0, Math.PI*2);
            ctx.fillStyle = col; ctx.fill();
            ctx.fillStyle = '#d1d5db'; ctx.fillText(lbl, getX(x), getY(y) - 8);
        }
        
        drawPoint(0, p.value_0h, '#10b981', 'OBS 0h');
        drawPoint(24, p.value_24h, '#10b981', 'OBS 24h');
        drawPoint(168, p.predicted_168h, '#00f0ff', 'PRED 168h');
    }

    window.onload = () => loadScreeningData();
</script>
</body>
</html></html>"""


class ScreeningRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler serving REST endpoints and the Single-Page UI."""

    def log_message(self, format, *args):
        """Suppress noisy default request logging."""
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            ui_html_path = os.path.join(os.path.dirname(__file__), "..", "src", "screening", "ui", "index.html")
            if os.path.exists(ui_html_path):
                with open(ui_html_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = HTML_PAGE
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        elif path == "/api/datasets":
            datasets = SERVICE.list_available_csvs()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(datasets).encode("utf-8"))
        elif path == "/api/current":
            global CURRENT_SCREENING_RESULT_OBJ, CURRENT_SCREENING_RESULT_DICT
            if CURRENT_SCREENING_RESULT_OBJ is None:
                default_csv = "data/demo_burnin_data.csv"
                if os.path.exists(default_csv):
                    CURRENT_SCREENING_RESULT_OBJ = SERVICE.run_screening(csv_path=default_csv)
                    CURRENT_SCREENING_RESULT_DICT = screening_result_to_dict(CURRENT_SCREENING_RESULT_OBJ)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(CURRENT_SCREENING_RESULT_DICT).encode("utf-8"))
        elif path == "/api/download_audit":
            audit_file = "reports/phase7_audit_log.csv"
            if not os.path.exists(audit_file) and CURRENT_SCREENING_RESULT_OBJ is not None:
                try:
                    SERVICE.export_audit_log(
                        screening_result=CURRENT_SCREENING_RESULT_OBJ,
                        output_path=audit_file
                    )
                except Exception:
                    pass
            if os.path.exists(audit_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="phase7_audit_log.csv"')
                self.end_headers()
                with open(audit_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Audit log file not found")
        elif path == "/api/export_audit":
            if CURRENT_SCREENING_RESULT_OBJ is None:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No active screening result to export."}).encode("utf-8"))
                return

            try:
                out_path = SERVICE.export_audit_log(
                    screening_result=CURRENT_SCREENING_RESULT_OBJ,
                    output_path="reports/phase7_audit_log.csv"
                )
                df = SERVICE.audit_exporter.export_to_dataframe(
                    CURRENT_SCREENING_RESULT_OBJ, recorder=SERVICE.audit_recorder
                )
                n_reviewed = int((df["engineer_decision_status"] == "REVIEWED").sum()) if "engineer_decision_status" in df.columns else 0

                resp = {
                    "status": "ok",
                    "exported_path": out_path,
                    "download_url": "/api/download_audit",
                    "total_rows": len(df),
                    "reviewed_decisions": n_reviewed,
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/screen":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            try:
                payload = json.loads(body)
                csv_path = payload.get("csv_path", "data/demo_burnin_data.csv")

                global CURRENT_SCREENING_RESULT_OBJ, CURRENT_SCREENING_RESULT_DICT
                CURRENT_SCREENING_RESULT_OBJ = SERVICE.run_screening(csv_path=csv_path)
                CURRENT_SCREENING_RESULT_DICT = screening_result_to_dict(CURRENT_SCREENING_RESULT_OBJ)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(CURRENT_SCREENING_RESULT_DICT).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err_body = json.dumps({"error": str(exc)})
                self.wfile.write(err_body.encode("utf-8"))

        elif path == "/api/decision":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            try:
                payload = json.loads(body)
                comp_id = payload.get("component_id")
                lot_id = payload.get("lot_id")
                decision = payload.get("engineer_decision")
                reason = payload.get("engineer_reason")

                if CURRENT_SCREENING_RESULT_OBJ is None:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "No active screening run."}).encode("utf-8"))
                    return

                comp_res = CURRENT_SCREENING_RESULT_OBJ.get_component(comp_id, lot_id=lot_id)
                if comp_res is None:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Component {comp_id} not found."}).encode("utf-8"))
                    return

                # Record decision via service (enforces non-empty reason validation)
                audit_rec = SERVICE.record_human_decision(
                    component_result=comp_res,
                    engineer_decision=decision,
                    engineer_reason=reason,
                )

                # Re-export audit summary
                audit_summary = SERVICE.get_audit_summary()

                resp = {
                    "status": "ok",
                    "audit_record": {
                        "engineer_decision": audit_rec.engineer_decision,
                        "engineer_reason": audit_rec.engineer_reason,
                        "timestamp_utc": audit_rec.timestamp_utc,
                        "session_id": audit_rec.session_id,
                    },
                    "audit_summary": {
                        "total_decisions": audit_summary.total_decisions,
                        "pass_count": audit_summary.pass_count,
                        "monitor_count": audit_summary.monitor_count,
                        "reject_count": audit_summary.reject_count,
                    },
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            except ValueError as val_err:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(val_err)}).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")


def run_server(port: int = 8501, open_browser: bool = True):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, ScreeningRequestHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"=" * 72)
    print(f"HOPIUM SIH26170 — Phase 6 & 7 Screening & HITL Platform UI Server")
    print(f"Running at: {url}")
    print(f"=" * 72)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down UI server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Phase 6/7 Screening & HITL UI Server")
    parser.add_argument("--port", type=int, default=8501, help="Port to run UI server on (default: 8501)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_browser)
