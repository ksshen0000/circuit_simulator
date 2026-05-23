import { useState } from "react";
import { Toolbar } from "./components/Toolbar/Toolbar";
import { CircuitCanvas } from "./components/Canvas/CircuitCanvas";
import { SimulationControls } from "./components/SimulationControls/SimulationControls";
import { WaveformPanel } from "./components/WaveformPanel/WaveformPanel";
import { PropertyPanel } from "./components/PropertyPanel";

export default function App() {
  const [waveformHeight, setWaveformHeight] = useState(220);
  const [showProps, setShowProps] = useState(true);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <Toolbar />

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {showProps && (
          <div style={{
            width: 200, borderRight: "1px solid #e2e8f0", overflowY: "auto",
            background: "#fafafa", flexShrink: 0,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 10px", borderBottom: "1px solid #e2e8f0" }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>属性</span>
              <button onClick={() => setShowProps(false)} style={{ fontSize: 11, border: "none", background: "none", cursor: "pointer", color: "#94a3b8" }}>×</button>
            </div>
            <PropertyPanel />
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
          <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
            {!showProps && (
              <button
                onClick={() => setShowProps(true)}
                style={{
                  position: "absolute", top: 8, left: 8, zIndex: 10,
                  padding: "3px 8px", fontSize: 11, borderRadius: 4,
                  border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer",
                }}
              >
                属性
              </button>
            )}
            <CircuitCanvas />
          </div>

          <div
            style={{ height: 4, background: "#e2e8f0", cursor: "row-resize", flexShrink: 0 }}
            onMouseDown={(e) => {
              const startY = e.clientY;
              const startH = waveformHeight;
              const onMove = (ev: MouseEvent) => setWaveformHeight(Math.max(100, Math.min(500, startH - (ev.clientY - startY))));
              const onUp = () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
              window.addEventListener("mousemove", onMove);
              window.addEventListener("mouseup", onUp);
            }}
          />

          <div style={{ height: waveformHeight, borderTop: "1px solid #e2e8f0", overflow: "hidden" }}>
            <WaveformPanel />
          </div>
        </div>
      </div>

      <SimulationControls />
    </div>
  );
}
