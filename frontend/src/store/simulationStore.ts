import { create } from "zustand";
import type {
  SimulationSettings, SimulationResult, WaveformSignal,
} from "../types/simulation";
import { useCircuitStore } from "./circuitStore";
import { buildNetlist } from "../utils/netlist";
import { buildSignal, type SignalMode } from "../utils/signals";

const COLORS = [
  "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
  "#a855f7", "#06b6d4", "#ec4899", "#84cc16",
];

interface SimulationStore {
  settings: SimulationSettings;
  result: SimulationResult | null;
  isLoading: boolean;
  error: string | null;
  signals: WaveformSignal[];
  signalMode: SignalMode;
  cursorIndex: number | null;

  setSettings: (s: SimulationSettings) => void;
  runSimulation: () => Promise<void>;
  runSpiceText: (text: string, settings: SimulationSettings) => Promise<void>;
  addSignal: (key: string) => void;
  removeSignal: (key: string) => void;
  clearSignals: () => void;
  setSignalMode: (mode: SignalMode) => void;
  setCursorIndex: (index: number | null) => void;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function toResult(raw: Record<string, unknown>): SimulationResult {
  return {
    mode: raw.mode as SimulationResult["mode"],
    xValues: raw.x_values as number[],
    nodeVoltages: raw.node_voltages as Record<string, number[]>,
    nodeVoltagesMag: raw.node_voltages_mag as Record<string, number[]> | undefined,
    nodeVoltagesPhase: raw.node_voltages_phase as Record<string, number[]> | undefined,
    branchCurrents: raw.branch_currents as Record<string, number[]>,
    branchCurrentsMag: raw.branch_currents_mag as Record<string, number[]> | undefined,
    branchCurrentsPhase: raw.branch_currents_phase as Record<string, number[]> | undefined,
    error: raw.error as string | undefined,
  };
}

async function errorMessage(res: Response): Promise<string> {
  const err = await res.json().catch(() => ({ detail: res.statusText }));
  return Array.isArray(err.detail)
    ? err.detail.map((item: { msg: string }) => item.msg).join("; ")
    : err.detail ?? "Simulation failed";
}

export const useSimulationStore = create<SimulationStore>((set, get) => ({
  settings: { mode: "dc" },
  result: null,
  isLoading: false,
  error: null,
  signals: [],
  signalMode: "mag",
  cursorIndex: null,

  setSettings: (s) => set({ settings: s }),

  runSimulation: async () => {
    const { elements, nodes } = useCircuitStore.getState();
    const { settings } = get();
    set({ isLoading: true, error: null, result: null, signals: [], cursorIndex: null });

    try {
      const req = buildNetlist(elements, nodes, settings);
      const res = await fetch(`${API_URL}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });

      if (!res.ok) throw new Error(await errorMessage(res));

      const result = toResult(await res.json());
      set({ result, isLoading: false, signals: [], cursorIndex: null, signalMode: "mag" });
    } catch (e: unknown) {
      set({ error: (e as Error).message, isLoading: false });
    }
  },

  runSpiceText: async (text, settings) => {
    set({ isLoading: true, error: null, result: null, signals: [], cursorIndex: null });
    try {
      const res = await fetch(`${API_URL}/simulate/spice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      const result = toResult(await res.json());
      set({ result, settings, isLoading: false, signals: [], cursorIndex: null, signalMode: "mag" });
    } catch (e: unknown) {
      set({ error: (e as Error).message, isLoading: false });
    }
  },

  addSignal: (key) => {
    const { result, signals, signalMode } = get();
    if (!result || signals.find((s) => s.key === key)) return;

    const color = COLORS[signals.length % COLORS.length];
    const { data, unit } = buildSignal(result, key, signalMode);
    const signal: WaveformSignal = { key, label: key, data, color, unit };
    set({ signals: [...signals, signal] });
  },

  removeSignal: (key) => set((s) => ({ signals: s.signals.filter((sg) => sg.key !== key) })),
  clearSignals: () => set({ signals: [], cursorIndex: null }),

  setSignalMode: (mode) => {
    const { result, signals } = get();
    if (!result) {
      set({ signalMode: mode });
      return;
    }
    set({
      signalMode: mode,
      signals: signals.map((signal) => {
        const { data, unit } = buildSignal(result, signal.key, mode);
        return { ...signal, data, unit };
      }),
    });
  },

  setCursorIndex: (index) => set({ cursorIndex: index }),
}));
