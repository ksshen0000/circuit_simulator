import type { SimulationResult } from "../types/simulation";

/** Index to display for a mode-aware value (DC: 0, AC: first point or cursor,
 * transient: last point or cursor). */
export function sampleIndex(result: SimulationResult | null, cursorIndex: number | null): number {
  if (!result) return 0;
  if (result.mode === "dc") return 0;
  if (cursorIndex !== null && cursorIndex >= 0 && cursorIndex < result.xValues.length) return cursorIndex;
  return result.mode === "ac" ? 0 : Math.max(0, result.xValues.length - 1);
}

export function nearestSample(xs: number[], x: number): number {
  if (xs.length === 0) return 0;
  let best = 0;
  let bestDistance = Math.abs(xs[0] - x);
  for (let i = 1; i < xs.length; i += 1) {
    const distance = Math.abs(xs[i] - x);
    if (distance < bestDistance) {
      best = i;
      bestDistance = distance;
    }
  }
  return best;
}

export function nodeValueAt(result: SimulationResult, nodeId: string, index: number): number {
  const values = result.mode === "ac"
    ? result.nodeVoltagesMag?.[nodeId] ?? result.nodeVoltages[nodeId]
    : result.nodeVoltages[nodeId];
  return values?.[index] ?? 0;
}

export function formatEngineering(value: number, unit: string, digits = 3): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return `0${unit}`;
  const absolute = Math.abs(value);
  const scales: [number, string][] = [
    [1e9, "G"], [1e6, "M"], [1e3, "k"], [1, ""],
    [1e-3, "m"], [1e-6, "μ"], [1e-9, "n"], [1e-12, "p"],
  ];
  for (const [scale, prefix] of scales) {
    if (absolute >= scale || scale === 1e-12) {
      return `${(value / scale).toPrecision(digits)}${prefix}${unit}`;
    }
  }
  return `${value.toPrecision(digits)}${unit}`;
}

export function formatNodeVoltage(value: number): string {
  return formatEngineering(value, "V");
}

export function formatCursorX(result: SimulationResult, index: number): string {
  const x = result.xValues[index] ?? 0;
  if (result.mode === "ac") return formatFrequency(x);
  if (result.mode === "transient") return formatTime(x);
  return "DC";
}

export function formatFrequency(f: number): string {
  return `${formatEngineering(f, "Hz")}`;
}

export function formatTime(t: number): string {
  return `${formatEngineering(t, "s")}`;
}
