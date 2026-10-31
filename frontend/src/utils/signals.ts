import type { SimulationResult } from "../types/simulation";

export type SignalMode = "mag" | "phase" | "db";

export interface SignalData {
  data: { x: number; y: number }[];
  unit: string;
}

function branchValues(result: SimulationResult, id: string): number[] {
  return result.branchCurrents[id] ?? [];
}

function nodeValues(result: SimulationResult, id: string): number[] {
  return result.nodeVoltages[id] ?? [];
}

export function signalValues(
  result: SimulationResult,
  key: string,
  mode: SignalMode,
): { values: number[]; unit: string } {
  const isVoltage = key.startsWith("V(");
  const id = key.slice(2, -1);
  const ac = result.mode === "ac";
  if (ac) {
    const mag = isVoltage
      ? result.nodeVoltagesMag?.[id] ?? nodeValues(result, id)
      : result.branchCurrentsMag?.[id] ?? branchValues(result, id);
    const phase = isVoltage
      ? result.nodeVoltagesPhase?.[id] ?? []
      : result.branchCurrentsPhase?.[id] ?? [];
    if (mode === "phase") return { values: phase, unit: "°" };
    if (mode === "db") return { values: mag.map((value) => 20 * Math.log10(Math.max(Math.abs(value), 1e-12))), unit: "dB" };
    return { values: mag, unit: isVoltage ? "V" : "A" };
  }
  return {
    values: isVoltage ? nodeValues(result, id) : branchValues(result, id),
    unit: isVoltage ? "V" : "A",
  };
}

export function buildSignal(result: SimulationResult, key: string, mode: SignalMode): SignalData {
  const { values, unit } = signalValues(result, key, mode);
  return {
    data: result.xValues.map((x, index) => ({ x, y: values[index] ?? 0 })),
    unit,
  };
}
