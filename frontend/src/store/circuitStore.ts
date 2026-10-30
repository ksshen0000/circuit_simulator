import { create } from "zustand";
import { v4 as uuid } from "uuid";
import {
  type CircuitElement, type Wire, type CircuitNode, type ComponentType, type Rotation,
  type GridPoint, terminalPositions, opampTerminals,
} from "../types/circuit";
import { computeNodes } from "../utils/graphUtils";

interface CircuitStore {
  elements: Record<string, CircuitElement>;
  wires: Record<string, Wire>;
  nodes: Record<string, CircuitNode>;
  groundElementId: string | null;
  selectedIds: Set<string>;
  labelCounters: Record<string, number>;

  // persistence metadata
  currentCircuitId: string | null;
  currentCircuitName: string;
  setCircuitMeta: (id: string | null, name: string) => void;

  addElement: (type: ComponentType, center: GridPoint) => string;
  moveElement: (id: string, newCenter: GridPoint) => void;
  rotateElement: (id: string) => void;
  updateElement: (id: string, patch: Partial<CircuitElement>) => void;
  deleteElement: (id: string) => void;

  addWire: (points: GridPoint[]) => void;
  deleteWire: (id: string) => void;

  setSelected: (ids: string[]) => void;
  clearSelected: () => void;
  deleteSelected: () => void;

  recomputeNodes: () => void;
  clearAll: () => void;

  /** Replace the full circuit state (called after loading from backend). */
  loadFromData: (data: {
    elements: Record<string, CircuitElement>;
    wires: Record<string, Wire>;
    groundElementId: string | null;
  }) => void;
}

const DEFAULT_VALUES: Record<ComponentType, number> = {
  resistor: 1000,
  capacitor: 1e-6,
  inductor: 1e-3,
  voltage_source: 5,
  current_source: 0.001,
  ground: 0,
  opamp: 0,
};

const LABEL_PREFIXES: Record<ComponentType, string> = {
  resistor: "R",
  capacitor: "C",
  inductor: "L",
  voltage_source: "V",
  current_source: "I",
  ground: "GND",
  opamp: "U",
};

export const useCircuitStore = create<CircuitStore>((set, get) => ({
  elements: {},
  wires: {},
  nodes: {},
  groundElementId: null,
  selectedIds: new Set(),
  labelCounters: {},
  currentCircuitId: null,
  currentCircuitName: "未命名电路",

  setCircuitMeta: (id, name) => set({ currentCircuitId: id, currentCircuitName: name }),

  addElement: (type, center) => {
    const state = get();
    const prefix = LABEL_PREFIXES[type];
    const n = (state.labelCounters[prefix] ?? 0) + 1;
    const label = type === "ground" ? "GND" : `${prefix}${n}`;
    const id = uuid();
    const rotation: Rotation = 0;
    // Ground's connection point is at the element center itself (symbol draws downward)
    const [termA, termB, termOut] = type === "ground"
      ? [center, center]
      : type === "opamp" ? opampTerminals(center, rotation) : terminalPositions(center, rotation);

    const el: CircuitElement = {
      id, type, position: center, rotation,
      terminalA: termA, terminalB: termB, terminalOut: termOut,
      ...(type === "opamp" ? { openLoopGain: 1e5, gainBandwidth: 1e6, inputResistance: 1e9,
        outputResistance: 75, outputMin: -13.5, outputMax: 13.5, slewRate: 5e5, inputOffset: 0 } : {}),
      value: DEFAULT_VALUES[type],
      label,
      sourceWaveform: "dc",
      acPhase: 0,
    };

    set((s) => ({
      elements: { ...s.elements, [id]: el },
      labelCounters: { ...s.labelCounters, [prefix]: n },
      groundElementId: type === "ground" ? id : s.groundElementId,
    }));
    get().recomputeNodes();
    return id;
  },

  moveElement: (id, newCenter) => {
    set((s) => {
      const el = s.elements[id];
      if (!el) return s;
      const [termA, termB, termOut] = el.type === "ground"
        ? [newCenter, newCenter]
        : el.type === "opamp" ? opampTerminals(newCenter, el.rotation) : terminalPositions(newCenter, el.rotation);
      return {
        elements: { ...s.elements, [id]: { ...el, position: newCenter, terminalA: termA, terminalB: termB, terminalOut: termOut } },
      };
    });
    get().recomputeNodes();
  },

  rotateElement: (id) => {
    set((s) => {
      const el = s.elements[id];
      if (!el) return s;
      const newRot = ((el.rotation + 90) % 360) as Rotation;
      const [termA, termB, termOut] = el.type === "ground" ? [el.position, el.position] : el.type === "opamp" ? opampTerminals(el.position, newRot) : terminalPositions(el.position, newRot);
      return {
        elements: { ...s.elements, [id]: { ...el, rotation: newRot, terminalA: termA, terminalB: termB, terminalOut: termOut } },
      };
    });
    get().recomputeNodes();
  },

  updateElement: (id, patch) => {
    set((s) => ({
      elements: { ...s.elements, [id]: { ...s.elements[id], ...patch } },
    }));
  },

  deleteElement: (id) => {
    set((s) => {
      const { [id]: _, ...rest } = s.elements;
      return {
        elements: rest,
        groundElementId: s.groundElementId === id ? null : s.groundElementId,
      };
    });
    get().recomputeNodes();
  },

  addWire: (points) => {
    const id = uuid();
    set((s) => ({ wires: { ...s.wires, [id]: { id, points } } }));
    get().recomputeNodes();
  },

  deleteWire: (id) => {
    set((s) => {
      const { [id]: _, ...rest } = s.wires;
      return { wires: rest };
    });
    get().recomputeNodes();
  },

  setSelected: (ids) => set({ selectedIds: new Set(ids) }),
  clearSelected: () => set({ selectedIds: new Set() }),

  deleteSelected: () => {
    const { selectedIds, elements, wires } = get();
    const newElements = { ...elements };
    const newWires = { ...wires };
    let newGroundId = get().groundElementId;
    for (const id of selectedIds) {
      delete newElements[id];
      delete newWires[id];
      if (id === newGroundId) newGroundId = null;
    }
    set({ elements: newElements, wires: newWires, selectedIds: new Set(), groundElementId: newGroundId });
    get().recomputeNodes();
  },

  recomputeNodes: () => {
    const { elements, wires, groundElementId } = get();
    const nodes = computeNodes(elements, wires, groundElementId);
    set({ nodes });
  },

  clearAll: () => set({
    elements: {}, wires: {}, nodes: {}, groundElementId: null,
    selectedIds: new Set(), labelCounters: {},
    currentCircuitId: null, currentCircuitName: "未命名电路",
  }),

  loadFromData: ({ elements, wires, groundElementId }) => {
    // Rebuild labelCounters from the loaded labels so future additions don't collide
    const counters: Record<string, number> = {};
    for (const el of Object.values(elements)) {
      const prefix = el.label.replace(/\d+$/, "");
      const num = parseInt(el.label.replace(/\D/g, "") || "0", 10);
      if (!isNaN(num)) counters[prefix] = Math.max(counters[prefix] ?? 0, num);
    }
    set({ elements, wires, groundElementId, selectedIds: new Set(), labelCounters: counters });
    get().recomputeNodes();
  },
}));
