import { useState } from "react";
import { useSimulationStore } from "../../store/simulationStore";

export function SimulationControls() {
  const { settings, setSettings, runSimulation, isLoading, error } = useSimulationStore();
  const [mode, setMode] = useState<"dc" | "ac" | "transient">(settings.mode);

  const updateMode = (m: "dc" | "ac" | "transient") => {
    setMode(m);
    if (m === "dc") setSettings({ mode: "dc" });
    else if (m === "ac") setSettings({ mode: "ac", fStart: 1, fStop: 1e6, pointsPerDecade: 20, sweepType: "log" });
    else setSettings({ mode: "transient", tStop: 0.01, tStep: 1e-5, tStart: 0, method: "trapezoidal" });
  };

  const field = (label: string, value: number, onChange: (v: number) => void, step?: number) => (
    <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
      <span style={{ color: "#64748b", minWidth: 60 }}>{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ width: 90, padding: "2px 4px", border: "1px solid #e2e8f0", borderRadius: 4, fontSize: 12 }}
      />
    </label>
  );

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, padding: "6px 12px",
      background: "#fff", borderTop: "1px solid #e2e8f0", flexWrap: "wrap",
    }}>
      {/* Mode selector */}
      <div style={{ display: "flex", gap: 2 }}>
        {(["dc", "ac", "transient"] as const).map((m) => (
          <button
            key={m}
            onClick={() => updateMode(m)}
            style={{
              padding: "4px 10px", borderRadius: 5, fontSize: 12,
              border: "1px solid", cursor: "pointer",
              borderColor: mode === m ? "#3b82f6" : "#e2e8f0",
              background: mode === m ? "#eff6ff" : "#f8fafc",
              color: mode === m ? "#1d4ed8" : "#475569",
              fontWeight: mode === m ? 600 : 400,
            }}
          >
            {m.toUpperCase()}
          </button>
        ))}
      </div>

      <div style={{ width: 1, height: 24, background: "#e2e8f0" }} />

      {/* Mode-specific params */}
      {mode === "ac" && settings.mode === "ac" && (
        <>
          {field("起始频率", settings.fStart, (v) => setSettings({ ...settings, fStart: v }))}
          {field("截止频率", settings.fStop, (v) => setSettings({ ...settings, fStop: v }))}
          {field("点/decade", settings.pointsPerDecade, (v) => setSettings({ ...settings, pointsPerDecade: v }), 1)}
        </>
      )}
      {mode === "transient" && settings.mode === "transient" && (
        <>
          {field("结束时间", settings.tStop, (v) => setSettings({ ...settings, tStop: v }))}
          {field("步长", settings.tStep, (v) => setSettings({ ...settings, tStep: v }))}
        </>
      )}

      <button
        onClick={runSimulation}
        disabled={isLoading}
        style={{
          padding: "6px 16px", background: isLoading ? "#94a3b8" : "#3b82f6",
          color: "#fff", border: "none", borderRadius: 6, cursor: isLoading ? "not-allowed" : "pointer",
          fontWeight: 600, fontSize: 13,
        }}
      >
        {isLoading ? "计算中..." : "▶ 仿真"}
      </button>

      {error && (
        <span style={{ color: "#ef4444", fontSize: 12, maxWidth: 300 }}>错误: {error}</span>
      )}
    </div>
  );
}
