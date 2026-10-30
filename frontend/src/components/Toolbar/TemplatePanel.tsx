import { useState } from "react";
import { CIRCUIT_TEMPLATES, createCircuitTemplate, type CircuitTemplateId } from "../../data/circuitTemplates";
import { useCircuitStore } from "../../store/circuitStore";
import { useSimulationStore } from "../../store/simulationStore";
import { useUIStore } from "../../store/uiStore";

export function TemplatePanel() {
  const isLoading = useSimulationStore((state) => state.isLoading);
  const [selected, setSelected] = useState<CircuitTemplateId>("noninverting");
  const template = CIRCUIT_TEMPLATES.find((item) => item.id === selected)!;

  const load = () => {
    const circuit = useCircuitStore.getState();
    if ((Object.keys(circuit.elements).length || Object.keys(circuit.wires).length)
      && !confirm("载入标准电路将替换当前画布，未保存的修改会丢失。继续？")) return;
    circuit.loadFromData(createCircuitTemplate(selected));
    // A template becomes a new circuit, so saving cannot overwrite the previous one.
    circuit.setCircuitMeta(null, template.name);
    useSimulationStore.setState({ result: null, signals: [], error: null, settings: { mode: "dc" } });
    const ui = useUIStore.getState();
    ui.setTool("select");
    ui.setZoom(1);
    ui.setPan({ x: 20, y: 40 });
  };

  return <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
    <label htmlFor="circuit-template" style={{ fontSize: 12, color: "#64748b" }}>标准电路</label>
    <select id="circuit-template" value={selected} title={template.description}
      onChange={(event) => setSelected(event.target.value as CircuitTemplateId)}
      style={{ padding: "6px", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: 12 }}>
      {CIRCUIT_TEMPLATES.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
    <button onClick={load} disabled={isLoading} title={template.description}
      style={{ padding: "6px 10px", border: "1px solid #93c5fd", borderRadius: 6, background: "#eff6ff", color: "#1d4ed8", cursor: "pointer", whiteSpace: "nowrap" }}>
      载入模板
    </button>
  </div>;
}
