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
    <title>HOPIUM SIH26170 — Screening & HITL Audit Platform</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --card-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #38bdf8;
            --risk-low: #22c55e;
            --risk-medium: #eab308;
            --risk-high: #ef4444;
            --hitl-purple: #c084fc;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: var(--bg-color); color: var(--text-main); font-family: var(--font-family); line-height: 1.5; padding: 24px; }
        .container { max-width: 1400px; margin: 0 auto; }

        header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--card-border); margin-bottom: 24px; }
        header h1 { font-size: 1.5rem; font-weight: 700; color: var(--accent-blue); display: flex; align-items: center; gap: 8px; }
        header .badge { background: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; text-transform: uppercase; }

        .control-panel { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 20px; margin-bottom: 24px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
        .control-panel label { font-weight: 600; color: var(--text-muted); }
        select, button, input[type="file"], textarea { background: #0f172a; border: 1px solid var(--card-border); color: white; padding: 10px 14px; border-radius: 6px; font-size: 0.95rem; }
        button { cursor: pointer; }
        button.btn-primary { background: #0284c7; border: none; font-weight: 600; padding: 10px 20px; }
        button.btn-primary:hover { background: #0369a1; }
        button.btn-secondary { background: #475569; border: none; font-weight: 600; padding: 10px 16px; color: white; }
        button.btn-secondary:hover { background: #334155; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }

        .val-card { border-radius: 8px; padding: 16px; margin-bottom: 24px; border: 1px solid var(--card-border); }
        .val-pass { background: rgba(34, 197, 94, 0.1); border-color: var(--risk-low); color: #4ade80; }
        .val-fail { background: rgba(239, 68, 68, 0.1); border-color: var(--risk-high); color: #f87171; }

        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .metric-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 18px; text-align: center; }
        .metric-card .val { font-size: 2.2rem; font-weight: 800; margin-top: 4px; }
        .metric-card .lbl { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

        .main-layout { display: grid; grid-template-columns: 380px 1fr; gap: 24px; }
        @media (max-width: 1024px) { .main-layout { grid-template-columns: 1fr; } }

        .panel { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 20px; display: flex; flex-direction: column; }
        .panel-header { font-size: 1.1rem; font-weight: 700; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center; }

        .filter-bar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
        .filter-btn { padding: 4px 10px; font-size: 0.8rem; border-radius: 4px; border: 1px solid var(--card-border); background: #0f172a; color: var(--text-muted); }
        .filter-btn.active { background: #0284c7; border-color: #0284c7; color: white; }

        .comp-list { overflow-y: auto; max-height: 650px; display: flex; flex-direction: column; gap: 8px; }
        .comp-item { background: #0f172a; border: 1px solid var(--card-border); border-radius: 6px; padding: 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: all 0.15s; }
        .comp-item:hover, .comp-item.selected { border-color: var(--accent-blue); background: #1e293b; }
        .comp-item .id { font-weight: 600; font-size: 0.9rem; }
        .comp-item .sub { font-size: 0.75rem; color: var(--text-muted); }

        .tag { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
        .tag-LOW { background: rgba(34, 197, 94, 0.2); color: var(--risk-low); border: 1px solid var(--risk-low); }
        .tag-MEDIUM { background: rgba(234, 179, 8, 0.2); color: var(--risk-medium); border: 1px solid var(--risk-medium); }
        .tag-HIGH { background: rgba(239, 68, 68, 0.2); color: var(--risk-high); border: 1px solid var(--risk-high); }

        .tag-PASS { background: rgba(34, 197, 94, 0.3); color: #4ade80; border: 1px solid #4ade80; }
        .tag-MONITOR { background: rgba(234, 179, 8, 0.3); color: #facc15; border: 1px solid #facc15; }
        .tag-REJECT { background: rgba(239, 68, 68, 0.3); color: #f87171; border: 1px solid #f87171; }

        .section-header { font-size: 1rem; font-weight: 700; margin: 20px 0 10px 0; color: var(--accent-blue); display: flex; align-items: center; gap: 8px; border-bottom: 1px dashed var(--card-border); padding-bottom: 6px; }

        .hitl-panel { background: rgba(192, 132, 252, 0.05); border: 1px solid rgba(192, 132, 252, 0.3); border-radius: 8px; padding: 18px; margin-top: 24px; }
        .hitl-header { color: var(--hitl-purple); font-weight: 700; font-size: 1.05rem; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }

        .btn-decision { padding: 8px 16px; font-weight: 700; border-radius: 6px; border: 1px solid var(--card-border); background: #0f172a; color: var(--text-muted); cursor: pointer; transition: all 0.15s; }
        .btn-decision.sel-PASS { background: rgba(34, 197, 94, 0.2); border-color: var(--risk-low); color: var(--risk-low); }
        .btn-decision.sel-MONITOR { background: rgba(234, 179, 8, 0.2); border-color: var(--risk-medium); color: var(--risk-medium); }
        .btn-decision.sel-REJECT { background: rgba(239, 68, 68, 0.2); border-color: var(--risk-high); color: var(--risk-high); }

        .param-card { background: #0f172a; border: 1px solid var(--card-border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
        .param-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .param-title { font-weight: 700; font-size: 1.05rem; color: var(--accent-blue); }

        .param-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; font-size: 0.9rem; }
        .param-stat { background: #1e293b; padding: 8px 12px; border-radius: 6px; border: 1px solid #334155; }
        .param-stat .lbl { font-size: 0.75rem; color: var(--text-muted); }
        .param-stat .val { font-weight: 600; margin-top: 2px; }

        .chart-box { background: #090d16; border: 1px solid var(--card-border); border-radius: 6px; padding: 12px; height: 180px; width: 100%; margin-bottom: 12px; }

        .reason-box { background: rgba(234, 179, 8, 0.05); border: 1px solid rgba(234, 179, 8, 0.2); border-radius: 6px; padding: 12px; font-size: 0.85rem; }
        .reason-box ul { padding-left: 18px; margin-top: 6px; }

        .disclaimer { font-size: 0.75rem; color: var(--text-muted); font-style: italic; margin-top: 24px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>HOPIUM SIH26170 <span class="badge">Phase 6 & 7 Screening & HITL Platform</span></h1>
            <div style="font-size:0.85rem; color:var(--text-muted);">AI Advisory Screening + Human Engineering Signoff</div>
        </header>

        <div class="control-panel">
            <label for="csvSelect">Select Burn-In Dataset:</label>
            <select id="csvSelect">
                <option value="">-- Loading datasets --</option>
            </select>

            <button class="btn-primary" id="runBtn" onclick="runScreening()">Run Screening</button>
            <button class="btn-secondary" id="exportBtn" onclick="exportAuditCSV()" style="display:none;">Export Audit Log (CSV)</button>

            <span id="loadingSpinner" style="display:none; color:var(--accent-blue); font-size:0.9rem;">Processing Module A & B + Risk Engine...</span>
        </div>

        <div id="validationBox"></div>

        <div id="resultsContent" style="display:none;">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="lbl">Total Components</div>
                    <div class="val" id="metricTotal">0</div>
                </div>
                <div class="metric-card" style="border-color: var(--risk-low);">
                    <div class="lbl" style="color:var(--risk-low);">AI LOW Risk</div>
                    <div class="val" style="color:var(--risk-low);" id="metricLow">0</div>
                </div>
                <div class="metric-card" style="border-color: var(--risk-medium);">
                    <div class="lbl" style="color:var(--risk-medium);">AI MEDIUM Risk</div>
                    <div class="val" style="color:var(--risk-medium);" id="metricMed">0</div>
                </div>
                <div class="metric-card" style="border-color: var(--risk-high);">
                    <div class="lbl" style="color:var(--risk-high);">AI HIGH Risk</div>
                    <div class="val" style="color:var(--risk-high);" id="metricHigh">0</div>
                </div>
                <div class="metric-card" style="border-color: var(--hitl-purple);">
                    <div class="lbl" style="color:var(--hitl-purple);">Human Reviewed</div>
                    <div class="val" style="color:var(--hitl-purple);" id="metricReviewed">0 / 0</div>
                </div>
            </div>

            <div class="main-layout">
                <!-- Left Panel: Lot Command Center -->
                <div class="panel">
                    <div class="panel-header">
                        <span>Lot Command Center</span>
                        <select id="lotFilter" onchange="renderComponentList()" style="padding:4px 8px; font-size:0.8rem;">
                            <option value="ALL">All Lots</option>
                        </select>
                    </div>

                    <div class="filter-bar">
                        <button class="filter-btn active" onclick="setRiskFilter('ALL', this)">All</button>
                        <button class="filter-btn" onclick="setRiskFilter('ATTENTION', this)">Attention Only</button>
                        <button class="filter-btn" onclick="setRiskFilter('HIGH', this)">HIGH</button>
                        <button class="filter-btn" onclick="setRiskFilter('MEDIUM', this)">MEDIUM</button>
                        <button class="filter-btn" onclick="setRiskFilter('LOW', this)">LOW</button>
                    </div>

                    <div class="comp-list" id="compList"></div>
                </div>

                <!-- Right Panel: Component Analysis & Human Review -->
                <div class="panel">
                    <div class="panel-header">
                        <span>Component Analysis & Signoff</span>
                        <span id="compHeaderTag">Select a component</span>
                    </div>

                    <div id="compDetailBody">
                        <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
                            Select a component from the Lot Command Center to inspect its 168h drift predictions, population anomaly scores, explainable AI risk evidence, and record human engineering signoff.
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="disclaimer">
            PROTOTYPE ADVISORY & AUDIT PLATFORM ONLY. Human engineering signoff is the final decision authority. AI risk scores and predictions support human decision-making and do not replace certified component acceptance specifications.
        </div>
    </div>

    <script>
        let screeningData = null;
        let activeRiskFilter = 'ALL';
        let selectedCompId = null;
        let selectedLotId = null;
        let selectedDecision = 'PASS';

        async function loadDatasets() {
            try {
                const res = await fetch('/api/datasets');
                const list = await res.json();
                const sel = document.getElementById('csvSelect');
                sel.innerHTML = '';
                list.forEach(item => {
                    const opt = document.createElement('option');
                    opt.value = item.path;
                    opt.textContent = `${item.filename} (${(item.size_bytes / 1024).toFixed(1)} KB)`;
                    sel.appendChild(opt);
                });
            } catch (err) {
                console.error("Failed to list datasets", err);
            }
        }

        async function runScreening() {
            const path = document.getElementById('csvSelect').value;
            if (!path) return;

            document.getElementById('loadingSpinner').style.display = 'inline';
            document.getElementById('runBtn').disabled = true;

            try {
                const res = await fetch('/api/screen', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ csv_path: path })
                });
                screeningData = await res.json();
                renderAll();
            } catch (err) {
                alert("Error running screening: " + err);
            } finally {
                document.getElementById('loadingSpinner').style.display = 'none';
                document.getElementById('runBtn').disabled = false;
            }
        }

        async function exportAuditCSV() {
            try {
                const res = await fetch('/api/export_audit');
                const data = await res.json();
                if (data.status === 'ok') {
                    alert(`Audit Log successfully exported to CSV:\n\nPath: ${data.exported_path}\nTotal Rows: ${data.total_rows}\nReviewed Decisions: ${data.reviewed_decisions}`);
                } else {
                    alert("Export failed: " + data.error);
                }
            } catch (err) {
                alert("Error exporting audit CSV: " + err);
            }
        }

        function renderAll() {
            if (!screeningData) return;

            // Render Validation UX
            const valBox = document.getElementById('validationBox');
            if (screeningData.aborted || screeningData.validation_status === 'FAIL') {
                valBox.className = 'val-card val-fail';
                valBox.innerHTML = `
                    <h3>❌ Data Validation Failed (${screeningData.validation_hard_failures} Hard Failures)</h3>
                    <p>${screeningData.abort_reason || 'Validation checks failed. Screening was aborted.'}</p>
                    <ul style="margin-top:8px; padding-left:20px;">
                        ${(screeningData.validation_messages || []).map(m => `<li>${m}</li>`).join('')}
                    </ul>
                `;
                document.getElementById('resultsContent').style.display = 'none';
                document.getElementById('exportBtn').style.display = 'none';
                return;
            } else {
                valBox.className = 'val-card val-pass';
                valBox.innerHTML = `
                    <h3>✅ Phase 2 Data Validation Passed</h3>
                    <p>Dataset verified: 0 Hard Failures, ${screeningData.validation_warnings} Warnings. Proceeding to Module A & B screening and HITL Audit Trail.</p>
                `;
            }

            document.getElementById('resultsContent').style.display = 'block';
            document.getElementById('exportBtn').style.display = 'inline-block';

            // Metrics
            document.getElementById('metricTotal').textContent = screeningData.total_components;
            document.getElementById('metricLow').textContent = screeningData.risk_low_count;
            document.getElementById('metricMed').textContent = screeningData.risk_medium_count;
            document.getElementById('metricHigh').textContent = screeningData.risk_high_count;

            const nDec = (screeningData.audit_summary && screeningData.audit_summary.total_decisions) || 0;
            document.getElementById('metricReviewed').textContent = `${nDec} / ${screeningData.total_components}`;

            // Populate Lot filter dropdown
            const lotSel = document.getElementById('lotFilter');
            lotSel.innerHTML = '<option value="ALL">All Lots</option>';
            Object.keys(screeningData.lots).sort().forEach(lid => {
                const opt = document.createElement('option');
                opt.value = lid;
                opt.textContent = `Lot ${lid}`;
                lotSel.appendChild(opt);
            });

            renderComponentList();
        }

        function setRiskFilter(filter, btn) {
            activeRiskFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderComponentList();
        }

        function renderComponentList() {
            if (!screeningData) return;
            const container = document.getElementById('compList');
            container.innerHTML = '';

            const selectedLot = document.getElementById('lotFilter').value;
            let allComps = [];

            Object.entries(screeningData.lots).forEach(([lid, lot]) => {
                if (selectedLot === 'ALL' || selectedLot === lid) {
                    allComps.push(...lot.components);
                }
            });

            // Apply Risk Filter
            let filtered = allComps.filter(c => {
                if (activeRiskFilter === 'ALL') return true;
                if (activeRiskFilter === 'ATTENTION') return c.overall_risk_level === 'HIGH' || c.overall_risk_level === 'MEDIUM';
                return c.overall_risk_level === activeRiskFilter;
            });

            // Sort: HIGH first, then MEDIUM, then LOW
            const rank = { HIGH: 2, MEDIUM: 1, LOW: 0 };
            filtered.sort((a, b) => rank[b.overall_risk_level] - rank[a.overall_risk_level]);

            filtered.forEach(c => {
                const div = document.createElement('div');
                div.className = `comp-item ${selectedCompId === c.component_id ? 'selected' : ''}`;
                div.onclick = () => selectComponent(c.component_id, c.lot_id);

                let auditBadge = '';
                if (c.audit_record) {
                    const dec = c.audit_record.engineer_decision;
                    const icon = dec === 'PASS' ? '✓' : (dec === 'MONITOR' ? '👁' : '✕');
                    auditBadge = `<span class="tag tag-${dec}" style="margin-left:6px; font-size:0.7rem;">${icon} ${dec}</span>`;
                }

                div.innerHTML = `
                    <div>
                        <div class="id">${c.component_id} ${auditBadge}</div>
                        <div class="sub">Lot: ${c.lot_id} | State: ${c.anomaly_classification_state}</div>
                    </div>
                    <span class="tag tag-${c.overall_risk_level}">AI: ${c.overall_risk_level}</span>
                `;
                container.appendChild(div);
            });

            if (filtered.length > 0 && !selectedCompId) {
                selectComponent(filtered[0].component_id, filtered[0].lot_id);
            }
        }

        function selectComponent(compId, lotId) {
            selectedCompId = compId;
            selectedLotId = lotId;
            renderComponentList();

            const lot = screeningData.lots[lotId];
            if (!lot) return;
            const comp = lot.components.find(c => c.component_id === compId);
            if (!comp) return;

            document.getElementById('compHeaderTag').innerHTML = `<span class="tag tag-${comp.overall_risk_level}">AI: ${comp.overall_risk_level} RISK</span>`;

            const body = document.getElementById('compDetailBody');

            let html = `
                <!-- AI Screening Assessment Section -->
                <div style="background:#0f172a; padding:16px; border-radius:8px; border:1px solid var(--card-border); margin-bottom:20px;">
                    <div style="font-size:0.8rem; color:var(--accent-blue); text-transform:uppercase; font-weight:700; margin-bottom:4px;">AI Screening Assessment (Advisory)</div>
                    <div style="font-weight:700; font-size:1.1rem; margin-bottom:4px;">Component ${comp.component_id} (Lot ${comp.lot_id})</div>
                    <div style="font-size:0.9rem; color:var(--text-muted); margin-bottom:8px;">${comp.recommendation_context}</div>
                    <div style="font-size:0.8rem; color:var(--text-muted);">
                        Module A Anomaly Score: <strong>${comp.anomaly_score.toFixed(3)}</strong> | Classification: <strong>${comp.anomaly_classification_state}</strong>
                    </div>
                </div>
            `;

            if (comp.risk_reasons && comp.risk_reasons.length > 0) {
                html += `
                    <div class="reason-box" style="margin-bottom:20px;">
                        <strong>AI Evidence Reasons:</strong>
                        <ul>
                            ${comp.risk_reasons.map(r => `<li>${r}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }

            // Parameter Level Evidence Cards
            Object.entries(comp.parameters).forEach(([pName, p]) => {
                const specText = (p.synthetic_spec_max !== null) ? `[${p.synthetic_spec_min}, ${p.synthetic_spec_max}] ${p.unit}` : 'None';
                html += `
                    <div class="param-card">
                        <div class="param-header">
                            <span class="param-title">${pName} (${p.unit})</span>
                            <span class="tag tag-${p.parameter_risk_level}">AI: ${p.parameter_risk_level}</span>
                        </div>

                        <div class="param-grid">
                            <div class="param-stat">
                                <div class="lbl">Observed 0h</div>
                                <div class="val">${p.value_0h.toFixed(4)}</div>
                            </div>
                            <div class="param-stat">
                                <div class="lbl">Observed 24h</div>
                                <div class="val">${p.value_24h.toFixed(4)}</div>
                            </div>
                            <div class="param-stat">
                                <div class="lbl">Predicted 168h</div>
                                <div class="val" style="color:var(--accent-blue);">${p.predicted_168h.toFixed(4)}</div>
                            </div>
                            <div class="param-stat">
                                <div class="lbl">Interval [Lower, Upper]</div>
                                <div class="val">[${p.lower_bound_168h.toFixed(3)}, ${p.upper_bound_168h.toFixed(3)}]</div>
                            </div>
                            <div class="param-stat">
                                <div class="lbl">Spec Limit</div>
                                <div class="val">${specText}</div>
                            </div>
                            <div class="param-stat">
                                <div class="lbl">Pop Anomaly Score</div>
                                <div class="val">${p.population_anomaly_score.toFixed(3)}</div>
                            </div>
                        </div>

                        <!-- Canvas for Truthful Trajectory -->
                        <div class="chart-box">
                            <canvas id="chart_${pName}" width="600" height="150"></canvas>
                        </div>
                    </div>
                `;
            });

            // PHASE 7: Human Review & Engineering Signoff Panel (Distinct from AI Assessment)
            const existingAudit = comp.audit_record;
            const defaultDecision = existingAudit ? existingAudit.engineer_decision : (comp.overall_risk_level === 'LOW' ? 'PASS' : 'MONITOR');
            selectedDecision = defaultDecision;

            html += `
                <div class="hitl-panel">
                    <div class="hitl-header">
                        <span>📋 Engineer Final Decision (Human Signoff)</span>
                        <span style="font-size:0.8rem; font-weight:normal; color:var(--text-muted);">Human Authority Layer — Phase 7</span>
                    </div>

                    ${existingAudit ? `
                        <div style="background:#0f172a; border:1px solid var(--card-border); border-radius:6px; padding:14px; margin-bottom:14px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                                <span>Recorded Signoff Status: <strong class="tag tag-${existingAudit.engineer_decision}">${existingAudit.engineer_decision}</strong></span>
                                <span style="font-size:0.75rem; color:var(--text-muted);">${new Date(existingAudit.timestamp_utc).toLocaleString()}</span>
                            </div>
                            <div style="font-size:0.9rem; color:var(--text-main);">
                                <strong>Human Reason / Factors:</strong> ${existingAudit.engineer_reason}
                            </div>
                        </div>
                    ` : ''}

                    <div style="margin-bottom:12px;">
                        <label style="font-size:0.85rem; font-weight:600; color:var(--text-muted); display:block; margin-bottom:6px;">Select Final Engineering Decision:</label>
                        <div style="display:flex; gap:10px;">
                            <button type="button" class="btn-decision ${selectedDecision === 'PASS' ? 'sel-PASS' : ''}" id="btnPass" onclick="setDecision('PASS')">✓ PASS</button>
                            <button type="button" class="btn-decision ${selectedDecision === 'MONITOR' ? 'sel-MONITOR' : ''}" id="btnMonitor" onclick="setDecision('MONITOR')">👁 MONITOR</button>
                            <button type="button" class="btn-decision ${selectedDecision === 'REJECT' ? 'sel-REJECT' : ''}" id="btnReject" onclick="setDecision('REJECT')">✕ REJECT</button>
                        </div>
                    </div>

                    <div style="margin-bottom:14px;">
                        <label style="font-size:0.85rem; font-weight:600; color:var(--text-muted); display:block; margin-bottom:6px;">Mandatory Human Justification Notes / Factors:</label>
                        <textarea id="engineerReason" rows="3" style="width:100%; font-family:var(--font-family); font-size:0.9rem;" placeholder="Enter specific engineering factors, re-measurement findings, or rationale supporting your final signoff...">${existingAudit ? existingAudit.engineer_reason : ''}</textarea>
                        <div id="hitlError" style="display:none; color:var(--risk-high); font-size:0.8rem; margin-top:4px;">⚠️ Human reasoning is mandatory and cannot be empty or whitespace-only.</div>
                    </div>

                    <button class="btn-primary" onclick="submitDecision()" style="width:100%;">Submit Engineering Signoff Decision</button>
                </div>
            `;

            body.innerHTML = html;

            // Draw truthful time-series charts on canvas
            setTimeout(() => {
                Object.entries(comp.parameters).forEach(([pName, p]) => {
                    drawTruthfulChart(`chart_${pName}`, p);
                });
            }, 50);
        }

        function setDecision(dec) {
            selectedDecision = dec;
            ['PASS', 'MONITOR', 'REJECT'].forEach(d => {
                const b = document.getElementById(`btn${d.charAt(0) + d.slice(1).toLowerCase()}`);
                if (b) {
                    if (d === dec) b.className = `btn-decision sel-${d}`;
                    else b.className = 'btn-decision';
                }
            });
        }

        async function submitDecision() {
            const reason = document.getElementById('engineerReason').value.trim();
            const errBox = document.getElementById('hitlError');

            if (!reason) {
                errBox.style.display = 'block';
                return;
            }
            errBox.style.display = 'none';

            try {
                const res = await fetch('/api/decision', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        component_id: selectedCompId,
                        lot_id: selectedLotId,
                        engineer_decision: selectedDecision,
                        engineer_reason: reason,
                    })
                });
                const data = await res.json();
                if (res.status === 200) {
                    // Update local state and re-render
                    const lot = screeningData.lots[selectedLotId];
                    if (lot) {
                        const comp = lot.components.find(c => c.component_id === selectedCompId);
                        if (comp) {
                            comp.audit_record = data.audit_record;
                        }
                    }
                    if (data.audit_summary) {
                        screeningData.audit_summary = data.audit_summary;
                    }
                    const nDec = (screeningData.audit_summary && screeningData.audit_summary.total_decisions) || 0;
                    document.getElementById('metricReviewed').textContent = `${nDec} / ${screeningData.total_components}`;

                    selectComponent(selectedCompId, selectedLotId);
                } else {
                    alert("Error submitting decision: " + (data.error || "Unknown error"));
                }
            } catch (err) {
                alert("Failed to submit decision: " + err);
            }
        }

        function drawTruthfulChart(canvasId, p) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const w = canvas.width;
            const h = canvas.height;

            ctx.clearRect(0, 0, w, h);

            // Truthful points: 0h, 24h (observed), 168h (predicted point + interval)
            const y0 = p.value_0h;
            const y24 = p.value_24h;
            const y168 = p.predicted_168h;
            const yLower = p.lower_bound_168h;
            const yUpper = p.upper_bound_168h;

            let allY = [y0, y24, y168, yLower, yUpper];
            if (p.synthetic_spec_max !== null) allY.push(p.synthetic_spec_max);
            if (p.synthetic_spec_min !== null) allY.push(p.synthetic_spec_min);

            const minY = Math.min(...allY) * 0.95;
            const maxY = Math.max(...allY) * 1.05;

            function mapX(hours) {
                const pad = 50;
                return pad + (hours / 168) * (w - pad - 20);
            }
            function mapY(val) {
                const pad = 20;
                return h - pad - ((val - minY) / (maxY - minY + 1e-9)) * (h - 2 * pad);
            }

            // Draw Spec Line if available
            if (p.synthetic_spec_max !== null) {
                ctx.strokeStyle = '#ef4444';
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.moveTo(mapX(0), mapY(p.synthetic_spec_max));
                ctx.lineTo(mapX(168), mapY(p.synthetic_spec_max));
                ctx.stroke();
                ctx.fillStyle = '#ef4444';
                ctx.font = '10px sans-serif';
                ctx.fillText(`Spec Max (${p.synthetic_spec_max})`, mapX(0), mapY(p.synthetic_spec_max) - 4);
            }

            // Draw Prediction Interval Shading at 168h
            const x168 = mapX(168);
            ctx.fillStyle = 'rgba(56, 189, 248, 0.2)';
            ctx.fillRect(x168 - 6, mapY(yUpper), 12, mapY(yLower) - mapY(yUpper));
            ctx.strokeStyle = '#38bdf8';
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(x168 - 10, mapY(yUpper)); ctx.lineTo(x168 + 10, mapY(yUpper));
            ctx.moveTo(x168 - 10, mapY(yLower)); ctx.lineTo(x168 + 10, mapY(yLower));
            ctx.stroke();

            // Observed Trajectory (0h -> 24h solid green line)
            ctx.strokeStyle = '#22c55e';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(mapX(0), mapY(y0));
            ctx.lineTo(mapX(24), mapY(y24));
            ctx.stroke();

            // Predicted Path (24h -> 168h dashed blue line)
            ctx.strokeStyle = '#38bdf8';
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(mapX(24), mapY(y24));
            ctx.lineTo(mapX(168), mapY(y168));
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw Data Points
            function drawPoint(x, y, color, label) {
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(mapX(x), mapY(y), 4, 0, 2 * Math.PI);
                ctx.fill();
                ctx.fillStyle = '#f8fafc';
                ctx.font = '10px sans-serif';
                ctx.fillText(label, mapX(x) - 10, mapY(y) - 8);
            }

            drawPoint(0, y0, '#22c55e', `0h: ${y0.toFixed(2)}`);
            drawPoint(24, y24, '#22c55e', `24h: ${y24.toFixed(2)}`);
            drawPoint(168, y168, '#38bdf8', `168h pred: ${y168.toFixed(2)}`);
        }

        // Init
        loadDatasets();
    </script>
</body>
</html>
"""


class ScreeningRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler serving REST endpoints and the Single-Page UI."""

    def log_message(self, format, *args):
        """Suppress noisy default request logging."""
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif path == "/api/datasets":
            datasets = SERVICE.list_available_csvs()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(datasets).encode("utf-8"))
        elif path == "/api/current":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(CURRENT_SCREENING_RESULT_DICT).encode("utf-8"))
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
