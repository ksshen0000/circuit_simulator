import type { CircuitElement, CircuitNode } from "../types/circuit";
import type { SimulationSettings } from "../types/simulation";
import { pointToNode } from "./graphUtils";

export interface NetlistElementDTO {
  id: string;
  type: string;
  node_a: string;
  node_b: string;
  value: number;
  ac_amplitude?: number;
  ac_phase: number;
  source_waveform: string;
  sine_frequency?: number;
  pulse_period?: number;
  pulse_width?: number;
}

export interface SimulateRequest {
  elements: NetlistElementDTO[];
  ground_node: string;
  settings: Record<string, unknown>;
}

function settingsToDTO(s: SimulationSettings): Record<string, unknown> {
  if (s.mode === "dc") return { mode: "dc" };
  if (s.mode === "ac") return {
    mode: "ac",
    f_start: s.fStart,
    f_stop: s.fStop,
    points_per_decade: s.pointsPerDecade,
    sweep_type: s.sweepType,
  };
  return {
    mode: "transient",
    t_stop: s.tStop,
    t_step: s.tStep,
    t_start: s.tStart,
    method: s.method,
  };
}

export function buildNetlist(
  elements: Record<string, CircuitElement>,
  nodes: Record<string, CircuitNode>,
  settings: SimulationSettings,
): SimulateRequest {
  const dtos: NetlistElementDTO[] = [];

  for (const el of Object.values(elements)) {
    const nodeA = pointToNode(el.terminalA, nodes) ?? "?";
    const nodeB = el.type === "ground" ? "GND" : (pointToNode(el.terminalB, nodes) ?? "?");

    dtos.push({
      id: el.label,
      type: el.type,
      node_a: nodeA,
      node_b: nodeB,
      value: el.value,
      ac_amplitude: el.acAmplitude,
      ac_phase: el.acPhase,
      source_waveform: el.sourceWaveform,
      sine_frequency: el.sineFrequency,
      pulse_period: el.pulsePeriod,
      pulse_width: el.pulseWidth,
    });
  }

  return {
    elements: dtos,
    ground_node: "GND",
    settings: settingsToDTO(settings),
  };
}
