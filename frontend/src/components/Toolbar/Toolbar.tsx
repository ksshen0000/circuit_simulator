import { useUIStore } from "../../store/uiStore";
import { useCircuitStore } from "../../store/circuitStore";
import type { ComponentType } from "../../types/circuit";
import { SpicePanel } from "./SpicePanel";
import { TemplatePanel } from "./TemplatePanel";
import { SaveLoadPanel } from "./SaveLoadPanel";

const COMPONENTS: { type: ComponentType; label: string; icon: string }[] = [
  { type: "resistor", label: "电阻", icon: "R" },
  { type: "capacitor", label: "电容", icon: "C" },
  { type: "inductor", label: "电感", icon: "L" },
  { type: "voltage_source", label: "电压源", icon: "V" },
  { type: "current_source", label: "电流源", icon: "I" },
  { type: "opamp", label: "运算放大器", icon: "▷" },
  { type: "ground", label: "接地", icon: "⏚" },
];

export function Toolbar() {
  const { toolMode, pendingType, setTool } = useUIStore();
  const { clearAll } = useCircuitStore();

  const btn = (label: string, active: boolean, onClick: () => void, title?: string) => (
    <button
      key={label}
      title={title ?? label}
      onClick={onClick}
      style={{
        padding: "6px 10px",
        borderRadius: 6,
        border: "1px solid",
        borderColor: active ? "#3b82f6" : "#e2e8f0",
        background: active ? "#eff6ff" : "#fff",
        color: active ? "#1d4ed8" : "#334155",
        fontWeight: active ? 600 : 400,
        cursor: "pointer",
        fontSize: 13,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 4, padding: "6px 12px",
      background: "#fff", borderBottom: "1px solid #e2e8f0", flexWrap: "wrap",
    }}>
      <span style={{ fontSize: 12, color: "#94a3b8", marginRight: 4 }}>工具</span>
      {btn("选择 (S)", toolMode === "select", () => setTool("select"), "选择/移动 [S]")}
      {btn("导线 (W)", toolMode === "wire", () => setTool("wire"), "绘制导线 [W]")}
      {btn("平移", toolMode === "pan", () => setTool("pan"), "平移画布")}

      <div style={{ width: 1, height: 24, background: "#e2e8f0", margin: "0 4px" }} />
      <span style={{ fontSize: 12, color: "#94a3b8", marginRight: 4 }}>元件</span>

      {COMPONENTS.map(({ type, label, icon }) =>
        btn(
          `${icon} ${label}`,
          toolMode === "place" && pendingType === type,
          () => setTool("place", type),
        )
      )}

      <div style={{ width: 1, height: 24, background: "#e2e8f0", margin: "0 4px" }} />
      {btn("清空", false, () => { if (confirm("清空电路？")) clearAll(); })}

      <div style={{ width: 1, height: 24, background: "#e2e8f0", margin: "0 4px" }} />
      <SaveLoadPanel />
      <div style={{ width: 1, height: 24, background: "#e2e8f0", margin: "0 4px" }} />
      <TemplatePanel />
      <SpicePanel />

      <div style={{ marginLeft: "auto", fontSize: 11, color: "#94a3b8" }}>
        R=旋转 · Del=删除 · Esc=取消
      </div>
    </div>
  );
}
