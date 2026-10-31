import { useSimulationStore } from "../../store/simulationStore";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { lttb } from "../../utils/downsample";
import { downloadText, resultToCsv } from "../../utils/csv";
import { formatCursorX, formatEngineering } from "../../utils/display";

const MAX_CHART_POINTS = 4000;

export function WaveformPanel() {
  const {
    result, signals, addSignal, removeSignal, signalMode, setSignalMode,
    cursorIndex, setCursorIndex,
  } = useSimulationStore();

  if (!result) {
    return (
      <div style={{ padding: 16, color: "#94a3b8", fontSize: 13, textAlign: "center" }}>
        运行仿真后，点击节点或元件查看波形
      </div>
    );
  }

  const nodeKeys = Object.keys(result.nodeVoltages).map((id) => `V(${id})`);
  const branchKeys = Object.keys(result.branchCurrents).map((id) => `I(${id})`);
  const allKeys = [...nodeKeys, ...branchKeys];

  const isAC = result.mode === "ac";
  const isTransient = result.mode === "transient";
  const xLabel = isAC ? "频率 (Hz)" : isTransient ? "时间 (s)" : "直流";

  const chartData = result.xValues.map((x, i) => {
    const row: Record<string, number> = { x };
    for (const sig of signals) row[sig.key] = sig.data[i]?.y ?? 0;
    return row;
  });
  const sampledData = signals.length > 0 && chartData.length > MAX_CHART_POINTS
    ? lttb(chartData.map((row) => ({ x: row.x, y: row[signals[0].key] ?? 0, row })), MAX_CHART_POINTS)
      .map((point) => point.row)
    : chartData;

  const activeCursor = cursorIndex !== null && cursorIndex >= 0 && cursorIndex < result.xValues.length
    ? cursorIndex : null;
  const cursorX = activeCursor !== null ? result.xValues[activeCursor] : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#fff" }}>
      {/* Signal selector */}
      <div style={{ display: "flex", gap: 4, padding: "6px 12px", borderBottom: "1px solid #e2e8f0", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b", alignSelf: "center" }}>添加信号:</span>
        {allKeys.map((key) => {
          const active = signals.some((s) => s.key === key);
          return (
            <button
              key={key}
              onClick={() => active ? removeSignal(key) : addSignal(key)}
              style={{
                padding: "2px 8px", borderRadius: 4, fontSize: 11, cursor: "pointer",
                border: "1px solid",
                borderColor: active ? signals.find((s) => s.key === key)?.color ?? "#3b82f6" : "#e2e8f0",
                background: active ? (signals.find((s) => s.key === key)?.color ?? "#3b82f6") + "22" : "#f8fafc",
                color: active ? signals.find((s) => s.key === key)?.color ?? "#1d4ed8" : "#475569",
              }}
            >
              {key}
            </button>
          );
        })}
      </div>

      {/* Chart toolbar: AC display mode, cursor and export */}
      <div style={{ display: "flex", gap: 6, padding: "4px 12px", borderBottom: "1px solid #f1f5f9", alignItems: "center", flexWrap: "wrap" }}>
        {isAC && (
          <>
            <span style={{ fontSize: 11, color: "#64748b" }}>显示</span>
            {(["mag", "db", "phase"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setSignalMode(mode)}
                style={{
                  padding: "1px 7px", borderRadius: 4, fontSize: 11, cursor: "pointer",
                  border: "1px solid " + (signalMode === mode ? "#3b82f6" : "#e2e8f0"),
                  background: signalMode === mode ? "#eff6ff" : "#fff",
                  color: signalMode === mode ? "#1d4ed8" : "#475569",
                }}
              >
                {mode === "mag" ? "线性幅值" : mode === "db" ? "dB" : "相位"}
              </button>
            ))}
            <span style={{ width: 1, height: 16, background: "#e2e8f0" }} />
          </>
        )}
        {activeCursor === null ? (
          <button
            onClick={() => setCursorIndex(Math.floor(result.xValues.length / 2))}
            style={{ padding: "1px 7px", borderRadius: 4, fontSize: 11, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer" }}
          >
            放置光标
          </button>
        ) : (
          <>
            <span style={{ fontSize: 11, color: "#334155" }}>
              光标 {formatCursorX(result, activeCursor)}
            </span>
            <input
              aria-label="光标位置"
              type="range"
              min={0}
              max={Math.max(0, result.xValues.length - 1)}
              value={activeCursor}
              onChange={(event) => setCursorIndex(Number(event.target.value))}
              style={{ width: 150 }}
            />
            <button
              onClick={() => setCursorIndex(null)}
              style={{ padding: "1px 7px", borderRadius: 4, fontSize: 11, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer" }}
            >
              清除
            </button>
          </>
        )}
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#94a3b8" }}>
          {chartData.length} 点{chartData.length > MAX_CHART_POINTS && signals.length > 0 ? `（显示抽稀至 ${MAX_CHART_POINTS}）` : ""}
        </span>
        <button
          onClick={() => downloadText("simulation.csv", resultToCsv(result), "text/csv;charset=utf-8")}
          style={{ padding: "1px 7px", borderRadius: 4, fontSize: 11, border: "1px solid #3b82f6", background: "#eff6ff", color: "#1d4ed8", cursor: "pointer" }}
        >
          导出 CSV
        </button>
      </div>

      {/* Chart */}
      {signals.length === 0 ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: 13 }}>
          点击上方信号按钮选择要显示的波形
        </div>
      ) : (
        <div style={{ flex: 1, padding: "8px 4px 4px", minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sampledData} margin={{ top: 4, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="x"
                type="number"
                scale={isAC ? "log" : "linear"}
                domain={["dataMin", "dataMax"]}
                label={{ value: xLabel, position: "insideBottom", offset: -10, fontSize: 11 }}
                tickFormatter={(v: number) => isAC ? formatEngineering(v, "Hz") : isTransient ? formatEngineering(v, "s") : "DC"}
                tick={{ fontSize: 10 }}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                label={isAC
                  ? { value: signalMode === "db" ? "dB" : signalMode === "phase" ? "°" : "V/A", angle: -90, position: "insideLeft", fontSize: 10 }
                  : undefined}
              />
              <Tooltip
                formatter={(v: unknown, name: unknown) => [typeof v === "number" ? v.toPrecision(4) : String(v), String(name)] as [string, string]}
                labelFormatter={(l: unknown) => {
                  const n = Number(l);
                  return isAC ? formatEngineering(n, "Hz") : isTransient ? formatEngineering(n, "s") : "DC";
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {cursorX !== null && <ReferenceLine x={cursorX} stroke="#64748b" strokeDasharray="4 3" />}
              {signals.map((sig) => (
                <Line
                  key={sig.key}
                  type="monotone"
                  dataKey={sig.key}
                  stroke={sig.color}
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Cursor readout */}
      {activeCursor !== null && signals.length > 0 && (
        <div style={{ display: "flex", gap: 14, padding: "3px 12px", borderTop: "1px solid #f1f5f9", flexWrap: "wrap", fontSize: 11 }}>
          <span style={{ color: "#64748b" }}>{formatCursorX(result, activeCursor)}</span>
          {signals.map((sig) => (
            <span key={sig.key} style={{ color: sig.color }}>
              {sig.key} = {formatEngineering(sig.data[activeCursor]?.y ?? 0, sig.unit)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
