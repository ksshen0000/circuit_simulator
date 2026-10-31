import { useCircuitStore } from "../store/circuitStore";
import { useSimulationStore } from "../store/simulationStore";
import type { CircuitElement } from "../types/circuit";

export function PropertyPanel() {
  const { elements, selectedIds, updateElement } = useCircuitStore();
  const { result, addSignal } = useSimulationStore();

  if (selectedIds.size !== 1) {
    return (
      <div style={{ padding: 12, fontSize: 12, color: "#94a3b8" }}>
        选中一个元件查看属性
      </div>
    );
  }

  const id = [...selectedIds][0];
  const el = elements[id];
  if (!el) return null;

  const numField = (label: string, key: keyof CircuitElement, step?: number) => (
    <div key={key} style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 2 }}>{label}</label>
      <input
        type="number"
        step={step}
        value={(el[key] as number | undefined) ?? ""}
        onChange={(e) => updateElement(id, { [key]: e.target.value === "" ? undefined : Number(e.target.value) })}
        style={{ width: "100%", padding: "3px 6px", border: "1px solid #e2e8f0", borderRadius: 4, fontSize: 12 }}
      />
    </div>
  );

  const selectField = (label: string, key: "sourceWaveform", options: string[]) => (
    <div key={key} style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 2 }}>{label}</label>
      <select
        value={el[key]}
        onChange={(e) => updateElement(id, { [key]: e.target.value as CircuitElement["sourceWaveform"] })}
        style={{ width: "100%", padding: "3px 6px", border: "1px solid #e2e8f0", borderRadius: 4, fontSize: 12 }}
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );

  const mosTypeField = (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 2 }}>类型</label>
      <select
        value={el.mosType ?? "nmos"}
        onChange={(e) => updateElement(id, { mosType: e.target.value as "nmos" | "pmos" })}
        style={{ width: "100%", padding: "3px 6px", border: "1px solid #e2e8f0", borderRadius: 4, fontSize: 12 }}
      >
        <option value="nmos">NMOS</option>
        <option value="pmos">PMOS</option>
      </select>
    </div>
  );

  const VALUE_LABELS: Record<string, string> = {
    resistor: "电阻 (Ω)", capacitor: "电容 (F)", inductor: "电感 (H)",
    voltage_source: "DC 电压 / 阶跃高值 (V)", current_source: "DC 电流 / 阶跃高值 (A)", ground: "-",
  };

  return (
    <div style={{ padding: 12, fontSize: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 10, color: "#1e293b" }}>{el.label} — {el.type}</div>

      {el.type !== "ground" && el.type !== "opamp" && el.type !== "mosfet" && el.type !== "diode"
        && numField(VALUE_LABELS[el.type] ?? "值", "value", 0.001)}

      {(el.type === "voltage_source" || el.type === "current_source") && (
        <>
          {numField("AC 小信号幅值", "acAmplitude", 0.1)}
          {numField("AC 相位 (°)", "acPhase", 1)}
          {numField("DC 值（留空沿用主值）", "dcValue", 0.1)}
          {selectField("波形", "sourceWaveform", ["dc", "sine", "pulse", "step"])}
          {el.sourceWaveform === "sine" && (
            <>
              {numField("瞬态幅值（留空沿用 AC）", "sineAmplitude", 0.1)}
              {numField("瞬态偏移", "sineOffset", 0.1)}
              {numField("频率 (Hz)", "sineFrequency", 1)}
              {numField("瞬态相位（留空沿用 AC）", "sinePhase", 1)}
              {numField("延迟 (s)", "sineDelay")}
              {numField("阻尼 (1/s)", "sineDamping")}
            </>
          )}
          {el.sourceWaveform === "pulse" && (
            <>
              {numField("周期 (s)", "pulsePeriod")}
              {numField("高电平宽度 (s)", "pulseWidth")}
              {numField("低电平", "pulseLow")}
              {numField("延迟 (s)", "pulseDelay")}
              {numField("上升时间 (s)", "pulseRise")}
              {numField("下降时间 (s)", "pulseFall")}
            </>
          )}
        </>
      )}

      {el.type === "diode" && <>
        <p style={{ color: "#64748b", fontSize: 11 }}>阳极 = 端子 A，阴极 = 端子 B。Shockley 指数模型。</p>
        {numField("饱和电流 IS (A)", "diodeIs", 1e-15)}
        {numField("发射系数 N", "diodeN", 0.1)}
      </>}

      {el.type === "mosfet" && <>
        <p style={{ color: "#64748b", fontSize: 11 }}>
          漏极 = 端子 A，源极 = 端子 B，栅极 = 第三端。Level-1 Shichman-Hodges 模型，体效应与反向导电未建模。
        </p>
        {mosTypeField}
        {numField("阈值电压 VTO (V)", "mosVto", 0.1)}
        {numField("跨导参数 KP (A/V²)", "mosKp", 1e-4)}
        {numField("沟道长度调制 λ (1/V)", "mosLambda", 0.001)}
        {numField("栅源电容 Cgs (F)", "mosCgs", 1e-12)}
        {numField("栅漏电容 Cgd (F)", "mosCgd", 1e-13)}
      </>}

      {el.type === "opamp" && <>
        <p style={{ color: "#64748b", fontSize: 11 }}>左上 +，左下 −，右侧输出。电源用对地输出上下限表示。</p>
        {numField("开环增益 (V/V)", "openLoopGain")}
        {numField("增益带宽积 (Hz)", "gainBandwidth")}
        {numField("差分输入电阻 (Ω)", "inputResistance")}
        {numField("输出电阻 (Ω)", "outputResistance")}
        {numField("输出下限 (V)", "outputMin")}
        {numField("输出上限 (V)", "outputMax")}
        {numField("压摆率 (V/s)", "slewRate")}
        {numField("输入失调 (V)", "inputOffset")}
      </>}

      {/* Simulation results for this element */}
      {result && (
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6 }}>仿真结果</div>
          {result.branchCurrents[el.label] && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: "#64748b" }}>电流: </span>
              <span style={{ color: "#1e293b" }}>
                {result.branchCurrents[el.label][0]?.toPrecision(4)} A
              </span>
            </div>
          )}
          <button
            onClick={() => addSignal(`I(${el.label})`)}
            style={{
              fontSize: 11, padding: "2px 8px", borderRadius: 4, border: "1px solid #3b82f6",
              background: "#eff6ff", color: "#1d4ed8", cursor: "pointer",
            }}
          >
            查看 I({el.label}) 波形
          </button>
        </div>
      )}
    </div>
  );
}
