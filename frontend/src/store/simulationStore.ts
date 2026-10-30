import { create } from "zustand";
import type {
  SimulationSettings, SimulationResult, WaveformSignal,
} from "../types/simulation";
import { useCircuitStore } from "./circuitStore";
import { buildNetlist } from "../utils/netlist";

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

  setSettings: (s: SimulationSettings) => void;
  runSimulation: () => Promise<void>;
  addSignal: (key: string) => void;
  removeSignal: (key: string) => void;
  clearSignals: () => void;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const useSimulationStore = create<SimulationStore>((set, get) => ({
  settings: { mode: "dc" },
  result: null,
  isLoading: false,
  error: null,
  signals: [],

  setSettings: (s) => set({ settings: s }),

  runSimulation: async () => {
    const { elements, nodes } = useCircuitStore.getState();
    const { settings } = get();
    set({ isLoading: true, error: null, result: null, signals: [] });

    try {
      const req = buildNetlist(elements, nodes, settings);
      const res = await fetch(`${API_URL}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(Array.isArray(err.detail)
          ? err.detail.map((item: { msg: string }) => item.msg).join("; ")
          : err.detail ?? "Simulation failed");
      }

      const raw = await res.json();
      const result: SimulationResult = {
        mode: raw.mode,
        xValues: raw.x_values,
        nodeVoltages: raw.node_voltages,
        nodeVoltagesMag: raw.node_voltages_mag,
        nodeVoltagesPhase: raw.node_voltages_phase,
        branchCurrents: raw.branch_currents,
        branchCurrentsMag: raw.branch_currents_mag,
        branchCurrentsPhase: raw.branch_currents_phase,
        error: raw.error,
      };

      set({ result, isLoading: false });
      // refresh existing signals with new data
      get().clearSignals();
    } catch (e: unknown) {
      set({ error: (e as Error).message, isLoading: false });
    }
  },

  addSignal: (key) => {
    const { result, signals } = get();
    if (!result || signals.find((s) => s.key === key)) return;

    const color = COLORS[signals.length % COLORS.length];
    let data: { x: number; y: number }[] = [];
    let unit = "";

    if (key.startsWith("V(")) {
      const nodeId = key.slice(2, -1);
      const vals = result.nodeVoltagesMag?.[nodeId] ?? result.nodeVoltages[nodeId] ?? [];
      data = result.xValues.map((x, i) => ({ x, y: vals[i] ?? 0 }));
      unit = "V";
    } else if (key.startsWith("I(")) {
      const elId = key.slice(2, -1);
      const vals = result.branchCurrentsMag?.[elId] ?? result.branchCurrents[elId] ?? [];
      data = result.xValues.map((x, i) => ({ x, y: vals[i] ?? 0 }));
      unit = "A";
    }

    const signal: WaveformSignal = { key, label: key, data, color, unit };
    set({ signals: [...signals, signal] });
  },

  removeSignal: (key) => set((s) => ({ signals: s.signals.filter((sg) => sg.key !== key) })),
  clearSignals: () => set({ signals: [] }),
}));
