export const GRID_SIZE = 20; // pixels per grid unit

export type GridPoint = { gx: number; gy: number };
export type Point = { x: number; y: number };
export type Rotation = 0 | 90 | 180 | 270;

export type ComponentType =
  | "resistor"
  | "capacitor"
  | "inductor"
  | "voltage_source"
  | "current_source"
  | "ground";

export type SourceWaveform = "dc" | "sine" | "pulse" | "step";

export interface CircuitElement {
  id: string;
  type: ComponentType;
  position: GridPoint;   // element center in grid coords
  rotation: Rotation;
  terminalA: GridPoint;  // absolute grid position of pin A
  terminalB: GridPoint;  // absolute grid position of pin B (ground has only A)
  value: number;         // SI: Ω / F / H / V / A
  label: string;
  sourceWaveform: SourceWaveform;
  acAmplitude?: number;
  acPhase: number;       // degrees
  sineFrequency?: number;
  pulsePeriod?: number;
  pulseWidth?: number;
}

export interface Wire {
  id: string;
  points: GridPoint[];   // rectilinear polyline, ≥2 points
}

export interface CircuitNode {
  id: string;            // "GND" | "N1" | "N2" ...
  gridPoints: GridPoint[];
}

export function gridToScreen(gp: GridPoint, pan: Point, zoom: number): Point {
  return { x: gp.gx * GRID_SIZE * zoom + pan.x, y: gp.gy * GRID_SIZE * zoom + pan.y };
}

export function screenToGrid(p: Point, pan: Point, zoom: number): GridPoint {
  return {
    gx: Math.round((p.x - pan.x) / (GRID_SIZE * zoom)),
    gy: Math.round((p.y - pan.y) / (GRID_SIZE * zoom)),
  };
}

export function terminalPositions(
  center: GridPoint,
  rotation: Rotation,
): [GridPoint, GridPoint] {
  // Pins are ±2 grid units from center along the element axis
  const offsets: Record<Rotation, [GridPoint, GridPoint]> = {
    0:   [{ gx: center.gx - 2, gy: center.gy }, { gx: center.gx + 2, gy: center.gy }],
    90:  [{ gx: center.gx, gy: center.gy - 2 }, { gx: center.gx, gy: center.gy + 2 }],
    180: [{ gx: center.gx + 2, gy: center.gy }, { gx: center.gx - 2, gy: center.gy }],
    270: [{ gx: center.gx, gy: center.gy + 2 }, { gx: center.gx, gy: center.gy - 2 }],
  };
  return offsets[rotation];
}

export function gpEqual(a: GridPoint, b: GridPoint): boolean {
  return a.gx === b.gx && a.gy === b.gy;
}

export function gpKey(p: GridPoint): string {
  return `${p.gx},${p.gy}`;
}
