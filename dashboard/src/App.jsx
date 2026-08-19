import { useState, useEffect } from "react";
import axios from "axios";

const API = "http://localhost:8000";
const KEY = "lh-test-key-123";
const headers = { "X-API-Key": KEY };

function StatusBadge({ status }) {
  const color = status === "error" ? "#e74c3c" : status === "success" ? "#27ae60" : "#f39c12";
  return (
    <span style={{
      background: color, color: "#fff", padding: "2px 8px",
      borderRadius: "4px", fontSize: "12px", fontWeight: "bold"
    }}>
      {status}
    </span>
  );
}

function ScoreCard({ label, score }) {
  if (score === null || score === undefined) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "#27ae60" : pct >= 40 ? "#f39c12" : "#e74c3c";
  return (
    <div style={{ flex: 1, background: "#f9f9f9", borderRadius: "6px", padding: "10px", textAlign: "center" }}>
      <div style={{ fontSize: "11px", color: "#888", marginBottom: "4px" }}>{label}</div>
      <div style={{ fontSize: "24px", fontWeight: "700", color }}>{pct}%</div>
      <div style={{ height: "4px", background: "#eee", borderRadius: "2px", marginTop: "6px" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: "2px" }} />
      </div>
    </div>
  );
}

function TraceDetail({ trace }) {
  const [spans, setSpans] = useState([]);

  useEffect(() => {
    if (!trace) { setSpans([]); return; }
    axios.get(`${API}/v1/traces/${trace.id}/spans`, { headers })
      .then(r => setSpans(r.data))
      .catch(() => setSpans([]));
  }, [trace]);

  if (!trace) return (
    <div style={{ color: "#888", textAlign: "center", padding: "40px" }}>
      ← Select a trace to see details
    </div>
  );

  const retrievalSpans = spans.filter(s => s.span_type === "retrieval");

  return (
    <div>
      <h2 style={{ color: "#0f3460", marginTop: 0 }}>{trace.name}</h2>
      <div style={{ marginBottom: "12px" }}>
        <StatusBadge status={trace.status} />
        <span style={{ marginLeft: "12px", color: "#666", fontSize: "14px" }}>
          {trace.span_count} spans · {new Date(trace.started_at).toLocaleString()}
        </span>
      </div>
      <div style={{
        background: "#f4f4f4", borderRadius: "6px",
        padding: "12px", fontFamily: "monospace", fontSize: "13px", marginBottom: "16px"
      }}>
        <div><strong>Trace ID:</strong> {trace.trace_id}</div>
        <div><strong>Duration:</strong> {trace.duration_ms ? `${trace.duration_ms}ms` : "—"}</div>
      </div>

      {retrievalSpans.length > 0 && (
        <div style={{
          background: "#fff", border: "1px solid #e0e0e0",
          borderRadius: "6px", padding: "12px", marginBottom: "10px"
        }}>
          <div style={{ fontWeight: "600", marginBottom: "8px", color: "#0f3460" }}>
            🔍 RAG Metrics
          </div>
          <div style={{ display: "flex", gap: "16px" }}>
            <ScoreCard label="Retrieval Relevance" score={retrievalSpans[0].retrieval_relevance_score} />
            <ScoreCard label="Groundedness" score={retrievalSpans[0].groundedness_score} />
          </div>
        </div>
      )}

      <div style={{ marginTop: "16px" }}>
        <div style={{ fontWeight: "600", color: "#0f3460", marginBottom: "8px" }}>Spans</div>
        {spans.map(s => (
          <div key={s.id} style={{
            background: s.error_text ? "#fff5f5" : "#f9f9f9",
            border: `1px solid ${s.error_text ? "#e74c3c" : "#e0e0e0"}`,
            borderRadius: "6px", padding: "10px", marginBottom: "6px",
            display: "flex", justifyContent: "space-between", alignItems: "center"
          }}>
            <div>
              <span style={{ fontWeight: "600", fontSize: "13px" }}>{s.name}</span>
              <span style={{ marginLeft: "8px", color: "#888", fontSize: "12px" }}>{s.span_type}</span>
              {s.error_text && <div style={{ color: "#e74c3c", fontSize: "12px", marginTop: "4px" }}>{s.error_text}</div>}
            </div>
            <span style={{ color: "#888", fontSize: "12px" }}>{s.duration_ms}ms</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TraceList({ onSelect, selected }) {
  const [traces, setTraces] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/v1/traces`, { headers })
      .then(r => setTraces(r.data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "#888" }}>Loading traces...</p>;
  if (traces.length === 0) return <p style={{ color: "#888" }}>No traces yet. Run your agent.</p>;

  return (
    <div>
      <h2 style={{ color: "#0f3460", marginTop: 0 }}>Traces</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#0f3460", color: "#fff" }}>
            <th style={th}>Agent</th>
            <th style={th}>Status</th>
            <th style={th}>Spans</th>
            <th style={th}>Started</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((t, i) => (
            <tr key={t.id}
              onClick={() => onSelect(t)}
              style={{
                background: selected?.id === t.id ? "#e8f4fd" : i % 2 === 0 ? "#fff" : "#f9f9f9",
                cursor: "pointer"
              }}>
              <td style={td}>{t.name}</td>
              <td style={td}><StatusBadge status={t.status} /></td>
              <td style={td}>{t.span_count}</td>
              <td style={td}>{new Date(t.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AlertsFeed() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/v1/alerts`, { headers })
      .then(r => setAlerts(r.data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "#888" }}>Loading alerts...</p>;

  return (
    <div>
      <h2 style={{ color: "#0f3460", marginTop: 0 }}>🚨 Alerts ({alerts.length})</h2>
      {alerts.length === 0 && <p style={{ color: "#888" }}>No alerts yet.</p>}
      {alerts.map(a => (
        <div key={a.id} style={{
          background: "#fff5f5", border: "1px solid #e74c3c",
          borderLeft: "4px solid #e74c3c", borderRadius: "6px",
          padding: "12px", marginBottom: "10px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong style={{ color: "#e74c3c" }}>{a.alert_type}</strong>
            <span style={{ fontSize: "12px", color: "#888" }}>
              {new Date(a.created_at).toLocaleString()}
            </span>
          </div>
          <p style={{ margin: "6px 0 0", color: "#333" }}>{a.message}</p>
        </div>
      ))}
    </div>
  );
}

const th = { padding: "10px 12px", textAlign: "left", fontWeight: "600" };
const td = { padding: "10px 12px", borderBottom: "1px solid #eee" };

export default function App() {
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState("traces");

  return (
    <div style={{ fontFamily: "Inter, sans-serif", minHeight: "100vh", background: "#f0f4ff" }}>
      <div style={{
        background: "#0f3460", color: "#fff",
        padding: "16px 32px", display: "flex", alignItems: "center", gap: "16px"
      }}>
        <span style={{ fontSize: "24px" }}>🔦</span>
        <h1 style={{ margin: 0, fontSize: "20px", fontWeight: "700" }}>Lighthouse AI</h1>
        <span style={{ fontSize: "13px", color: "#aac4ff" }}>RAG Agent Observability</span>
      </div>

      <div style={{ background: "#fff", borderBottom: "2px solid #e0e0e0", padding: "0 32px" }}>
        {["traces", "alerts"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: "none", border: "none", padding: "12px 20px",
            fontSize: "14px", fontWeight: tab === t ? "700" : "400",
            color: tab === t ? "#0f3460" : "#666",
            borderBottom: tab === t ? "2px solid #0f3460" : "2px solid transparent",
            cursor: "pointer", textTransform: "capitalize"
          }}>
            {t}
          </button>
        ))}
      </div>

      <div style={{
        padding: "24px 32px",
        display: "grid",
        gridTemplateColumns: tab === "traces" ? "1fr 380px" : "1fr",
        gap: "24px"
      }}>
        {tab === "traces" && (
          <>
            <div style={{ background: "#fff", borderRadius: "8px", padding: "20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
              <TraceList onSelect={setSelected} selected={selected} />
            </div>
            <div style={{ background: "#fff", borderRadius: "8px", padding: "20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
              <TraceDetail trace={selected} />
            </div>
          </>
        )}
        {tab === "alerts" && (
          <div style={{ background: "#fff", borderRadius: "8px", padding: "20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
            <AlertsFeed />
          </div>
        )}
      </div>
    </div>
  );
}
