import { useRef, useState } from "react";
import { useCircuitStore } from "../../store/circuitStore";
import { useSimulationStore } from "../../store/simulationStore";
import { useUIStore } from "../../store/uiStore";
import { buildNetlist } from "../../utils/netlist";
import { exportSpice, parseSpice, SPICE_EXAMPLE } from "../../utils/spice";

const buttonStyle = { padding: "6px 10px", borderRadius: 6, border: "1px solid #cbd5e1", background: "white", cursor: "pointer", fontSize: 12 };
const CANVAS_TYPES = new Set([
  "resistor", "capacitor", "inductor", "voltage_source", "current_source",
  "ground", "opamp", "mosfet", "diode",
]);

export function SpicePanel() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const isLoading = useSimulationStore((state) => state.isLoading);

  const readCanvas = async () => {
    setBusy(true);
    try {
      const circuit = useCircuitStore.getState();
      const simulation = useSimulationStore.getState();
      const value = Object.keys(circuit.elements).length
        ? await exportSpice(buildNetlist(circuit.elements, circuit.nodes, simulation.settings), circuit.currentCircuitName)
        : SPICE_EXAMPLE;
      setText(value);
      setError(null);
      setMessage("已从画布生成文本。导出包含电气连接，布局不会写入网表。");
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const show = () => {
    if (!text) readCanvas();
    setOpen(true);
  };
  const validate = async () => {
    const parsed = await parseSpice(text);
    setError(null);
    const unsupported = Object.values(parsed.elements).filter((el) => !CANVAS_TYPES.has(el.type));
    setMessage(unsupported.length
      ? `校验通过：${Object.keys(parsed.elements).length} 个元件；其中 ${unsupported.map((el) => el.type).join("、")} 可仿真/导出，但画布暂不支持放置。`
      : `校验通过：${Object.keys(parsed.elements).length} 个元件，分析模式 ${parsed.settings.mode}。`);
    return parsed;
  };
  const simulateText = async () => {
    setBusy(true);
    try {
      const parsed = await validate();
      await useSimulationStore.getState().runSpiceText(text, parsed.settings);
      const simulation = useSimulationStore.getState();
      if (simulation.error) setError(simulation.error);
      else {
        setMessage("已直接仿真文本电路；可在下方波形面板添加 V(...) / I(...) 信号。");
        setOpen(false);
      }
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const apply = async (run: boolean) => {
    setBusy(true);
    try {
      const parsed = await validate();
      const unsupported = Object.values(parsed.elements).filter((el) => !CANVAS_TYPES.has(el.type));
      if (unsupported.length) {
        throw new Error(`画布暂不支持 ${unsupported.map((el) => el.type).join("、")}；请使用「直接仿真」或下载 .cir`);
      }
      const circuit = useCircuitStore.getState();
      if ((Object.keys(circuit.elements).length || Object.keys(circuit.wires).length)
        && !confirm("应用文本将替换当前画布并自动排布。未保存的布局和修改会丢失，继续？")) return;
      circuit.loadFromData(parsed);
      circuit.setCircuitMeta(null, parsed.title);
      useSimulationStore.setState({ settings: parsed.settings, result: null, signals: [], error: null });
      const ui = useUIStore.getState();
      ui.setTool("select"); ui.setZoom(0.85); ui.setPan({ x: 30, y: 30 });
      setOpen(false);
      if (run) await useSimulationStore.getState().runSimulation();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const download = async () => {
    setBusy(true);
    try {
      await validate();
      const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url; link.download = "circuit.cir";
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };

  return <>
    <button onClick={show} style={buttonStyle}>文本电路 / SPICE</button>
    {open && <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "#0f172a88", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <section role="dialog" aria-modal="true" aria-labelledby="spice-title"
        onKeyDown={(event) => { event.stopPropagation(); if (event.key === "Escape") setOpen(false); }}
        style={{ width: 900, maxWidth: "100%", maxHeight: "95vh", overflow: "auto", background: "#fff", borderRadius: 10, padding: 20, boxShadow: "0 20px 60px #0004" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong id="spice-title">SPICE 文本电路</strong>
          <button onClick={() => setOpen(false)} style={buttonStyle} aria-label="关闭文本电路">关闭</button>
        </div>
        <p style={{ fontSize: 12, color: "#475569", lineHeight: 1.7 }}>
          支持 R/C/L、DC/AC/SIN/PULSE 独立源、内置 CS_OPAMP、NMOS/PMOS Level-1 MOSFET、
          二极管与 E/F/G/H 受控源，以及 .op / .ac dec|lin / .tran。
          支持 .param 表达式、.model 卡片和 .options RELTOL/ABSTOL；后缀 m = 毫，meg = 兆；节点 0 接地。
          E/F/G/H 受控源可校验、直接仿真和导出，但暂不支持放置到画布。
          当前不支持 .subckt / .include / .meas / .dc 或控制脚本；遇到不支持的语句会报行号。
          CS_OPAMP 属于本项目模型，外部 SPICE 需要另行提供模型库。
        </p>
        <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          <button style={buttonStyle} onClick={() => { if (!text || confirm("用画布内容替换当前文本草稿？")) readCanvas(); }}>从画布读取</button>
          <button style={buttonStyle} onClick={() => { if (!text || confirm("用示例替换当前文本草稿？")) { setText(SPICE_EXAMPLE); setError(null); setMessage(""); } }}>运放示例</button>
          <button style={buttonStyle} onClick={() => fileInput.current?.click()}>打开 .cir / .sp 文件</button>
          <button style={buttonStyle} onClick={() => void download()}>下载 .cir</button>
          <input ref={fileInput} type="file" accept=".cir,.sp,.spice,.txt" style={{ display: "none" }}
            onChange={async (event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (!file) return;
              if (file.size > 1_000_000) { setError("文件不能超过 1 MB"); return; }
              if (text && !confirm("用文件内容替换当前文本草稿？")) return;
              try { setText(await file.text()); setError(null); setMessage("文件已读入，尚未应用到画布。"); }
              catch (err) { setError(`读取失败：${(err as Error).message}`); }
            }} />
        </div>
        <textarea aria-label="SPICE 网表代码" disabled={busy} autoFocus spellCheck={false} value={text}
          onChange={(event) => { setText(event.target.value); setError(null); setMessage(""); }}
          style={{ width: "100%", boxSizing: "border-box", height: "45vh", minHeight: 200, resize: "vertical", padding: 12, border: "1px solid #cbd5e1", borderRadius: 6, fontFamily: "monospace", fontSize: 13, lineHeight: 1.65 }} />
        {error && <p role="alert" style={{ color: "#b91c1c", fontSize: 12 }}>{error}</p>}
        {message && <p role="status" style={{ color: "#047857", fontSize: 12 }}>{message}</p>}
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
          <button style={buttonStyle} onClick={() => { setBusy(true); void validate().catch((err: Error) => setError(err.message)).finally(() => setBusy(false)); }}>校验文本</button>
          <button style={buttonStyle} disabled={isLoading} onClick={() => void simulateText()}>直接仿真</button>
          <button style={buttonStyle} disabled={isLoading} onClick={() => void apply(false)}>应用到画布</button>
          <button style={{ ...buttonStyle, background: "#2563eb", color: "white" }} disabled={isLoading} onClick={() => void apply(true)}>应用并仿真</button>
        </div>
        </fieldset>
        {busy && <p role="status" style={{ fontSize: 12 }}>正在请求 Python 后端…</p>}
        <p style={{ color: "#64748b", fontSize: 11 }}>应用后自动排布元件，以节点标签连接。可以继续在画布编辑，也可重新读取为文本；SPICE 网表不保存画布布局。</p>
      </section>
    </div>}
  </>;
}
