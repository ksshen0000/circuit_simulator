export type SimulationMode = "dc" | "ac" | "transient";

export interface DCSettings { mode: "dc" }

export interface ACSettings {
  mode: "ac";
  fStart: number;
  fStop: number;
  pointsPerDecade: number;
  sweepType: "log" | "linear";
}

export interface TransientSettings {
  mode: "transient";
  tStop: number;
  tStep: number;
  tStart: number;
  method: "euler" | "trapezoidal";
}

export type SimulationSettings = DCSettings | ACSettings | TransientSettings;

export interface SimulationResult {
  mode: SimulationMode;
  xValues: number[];
  nodeVoltages: Record<string, number[]>;
  nodeVoltagesMag?: Record<string, number[]>;
  nodeVoltagesPhase?: Record<string, number[]>;
  branchCurrents: Record<string, number[]>;
  branchCurrentsMag?: Record<string, number[]>;
  branchCurrentsPhase?: Record<string, number[]>;
  error?: string;
}

export interface WaveformSignal {
  key: string;        // "V(N1)" | "I(R1)"
  label: string;
  data: { x: number; y: number }[];
  color: string;
  unit: string;
}
