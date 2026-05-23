import { create } from "zustand";
import type { ComponentType, Point } from "../types/circuit";

export type ToolMode = "select" | "wire" | "place" | "pan";

interface UIStore {
  toolMode: ToolMode;
  pendingType: ComponentType | null;
  zoom: number;
  pan: Point;
  showGrid: boolean;

  setTool: (mode: ToolMode, type?: ComponentType) => void;
  setZoom: (z: number) => void;
  setPan: (p: Point) => void;
  applyPanDelta: (dx: number, dy: number) => void;
  toggleGrid: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  toolMode: "select",
  pendingType: null,
  zoom: 1,
  pan: { x: 400, y: 300 },
  showGrid: true,

  setTool: (mode, type) => set({ toolMode: mode, pendingType: type ?? null }),
  setZoom: (z) => set({ zoom: Math.max(0.3, Math.min(3, z)) }),
  setPan: (p) => set({ pan: p }),
  applyPanDelta: (dx, dy) => set((s) => ({ pan: { x: s.pan.x + dx, y: s.pan.y + dy } })),
  toggleGrid: () => set((s) => ({ showGrid: !s.showGrid })),
}));
