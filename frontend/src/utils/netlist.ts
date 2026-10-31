import { elementTerminals, type CircuitElement, type CircuitNode } from "../types/circuit";
import type { SimulationSettings } from "../types/simulation";
import { pointToNode } from "./graphUtils";

export interface NetlistElementDTO {
  id: string;
  type: string;
  node_a: string;
  node_b: string;
  node_out?: string;
  node_g?: string;
  open_loop_gain?: number;
  gain_bandwidth?: number;
  input_resistance?: number;
  output_resistance?: number;
  output_min?: number;
  output_max?: number;
  slew_rate?: number;
  input_offset?: number;
  mos_type?: "nmos" | "pmos";
  mos_vto?: number;
  mos_kp?: number;
  mos_lambda?: number;
  mos_cgs?: number;
  mos_cgd?: number;
  diode_is?: number;
  diode_n?: number;
  value: number;
  ac_amplitude?: number;
  ac_phase: number;
  dc_value?: number;
  source_waveform: string;
  sine_frequency?: number;
  sine_amplitude?: number;
  sine_phase?: number;
  sine_offset?: number;
  sine_delay?: number;
  sine_damping?: number;
  pulse_low?: number;
  pulse_delay?: number;
  pulse_rise?: number;
  pulse_fall?: number;
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
    const pins = elementTerminals(el);
    const nodeA = pointToNode(pins[0], nodes) ?? "?";
    const nodeB = el.type === "ground" ? "GND" : (pointToNode(pins[1], nodes) ?? "?");

    dtos.push({
      id: el.label,
      type: el.type,
      node_a: nodeA,
      node_b: nodeB,
      node_out: el.type === "opamp" ? pointToNode(pins[2], nodes) ?? "?" : undefined,
      node_g: el.type === "mosfet" ? pointToNode(pins[2], nodes) ?? "?" : undefined,
      open_loop_gain: el.openLoopGain,
      gain_bandwidth: el.gainBandwidth,
      input_resistance: el.inputResistance,
      output_resistance: el.outputResistance,
      output_min: el.outputMin,
      output_max: el.outputMax,
      slew_rate: el.slewRate,
      input_offset: el.inputOffset,
      mos_type: el.mosType,
      mos_vto: el.mosVto,
      mos_kp: el.mosKp,
      mos_lambda: el.mosLambda,
      mos_cgs: el.mosCgs,
      mos_cgd: el.mosCgd,
      diode_is: el.diodeIs,
      diode_n: el.diodeN,
      value: el.value,
      ac_amplitude: el.acAmplitude,
      ac_phase: el.acPhase,
      dc_value: el.dcValue,
      source_waveform: el.sourceWaveform,
      sine_frequency: el.sineFrequency,
      sine_amplitude: el.sineAmplitude,
      sine_phase: el.sinePhase,
      sine_offset: el.sineOffset,
      sine_delay: el.sineDelay,
      sine_damping: el.sineDamping,
      pulse_low: el.pulseLow,
      pulse_delay: el.pulseDelay,
      pulse_rise: el.pulseRise,
      pulse_fall: el.pulseFall,
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
