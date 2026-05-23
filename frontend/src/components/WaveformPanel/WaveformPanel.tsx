import { useSimulationStore } from "../../store/simulationStore";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";

export function WaveformPanel() {
  const { result, signals, addSignal, removeSignal } = useSimulationStore();

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

  // Build merged chart data
  const chartData = result.xValues.map((x, i) => {
    const row: Record<string, number> = { x };
    for (const sig of signals) {
      row[sig.key] = sig.data[i]?.y ?? 0;
    }
    return row;
  });

  const xLabel = isAC ? "频率 (Hz)" : isTransient ? "时间 (s)" : "直流";

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

      {/* Chart */}
      {signals.length === 0 ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: 13 }}>
          点击上方信号按钮选择要显示的波形
        </div>
      ) : (
        <div style={{ flex: 1, padding: "8px 4px 4px" }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 4, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="x"
                type="number"
                scale={isAC ? "log" : "linear"}
                domain={["dataMin", "dataMax"]}
                label={{ value: xLabel, position: "insideBottom", offset: -10, fontSize: 11 }}
                tickFormatter={(v: number) => isAC ? formatFreq(v) : isTransient ? formatTime(v) : "DC"}
                tick={{ fontSize: 10 }}
              />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                formatter={(v: unknown, name: unknown) => [typeof v === "number" ? v.toPrecision(4) : String(v), String(name)] as [string, string]}
                labelFormatter={(l: unknown) => {
                  const n = Number(l);
                  return isAC ? formatFreq(n) : isTransient ? formatTime(n) : "DC";
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
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
    </div>
  );
}

function formatFreq(f: number): string {
  if (f >= 1e6) return `${(f / 1e6).toFixed(1)}M`;
  if (f >= 1e3) return `${(f / 1e3).toFixed(1)}k`;
  return `${f.toFixed(0)}`;
}

function formatTime(t: number): string {
  if (t >= 1) return `${t.toFixed(3)}s`;
  if (t >= 1e-3) return `${(t * 1e3).toFixed(2)}ms`;
  if (t >= 1e-6) return `${(t * 1e6).toFixed(2)}μs`;
  return `${(t * 1e9).toFixed(2)}ns`;
}
