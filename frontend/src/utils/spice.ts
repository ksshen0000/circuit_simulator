/** API client and canvas adapter only; SPICE syntax is owned by Python. */
import {
  type CircuitElement, type ComponentType, mosfetTerminals, opampTerminals, terminalPositions,
} from "../types/circuit";
import type { SimulationSettings } from "../types/simulation";
import type { SimulateRequest } from "./netlist";

export const SPICE_EXAMPLE = `* Non-inverting amplifier, gain 10
V1 in 0 DC 0.1 AC 1
XU1 in feedback out CS_OPAMP A0=100k GBW=1meg
R1 out feedback 9k
R2 feedback 0 1k
RL out 0 10k
.op
.end
`;

export interface ParsedSpiceDTO {
  title: string;
  request: SimulateRequest;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(30000),
    });
  } catch {
    throw new Error("无法连接 Python 后端，请确认 ./dev.sh 或后端服务已启动");
  }
  const result = await response.json();
  if (!response.ok) {
    throw new Error(Array.isArray(result.detail)
      ? result.detail.map((item: { msg: string }) => item.msg).join("; ")
      : result.detail ?? "SPICE 请求失败");
  }
  return result as T;
}

export function spiceToCanvas(parsed: ParsedSpiceDTO) {
  const elements: Record<string, CircuitElement> = {};
  for (const [index, el] of parsed.request.elements.entries()) {
    const position = { gx: 7 + index % 3 * 16, gy: 5 + Math.floor(index / 3) * 7 };
    const rotation = 0;
    const [terminalA, terminalB, terminalOut] = el.type === "opamp"
      ? opampTerminals(position, rotation)
      : el.type === "mosfet" ? mosfetTerminals(position, rotation)
        : terminalPositions(position, rotation);
    elements[el.id] = {
      id: el.id, label: el.id, type: el.type as ComponentType, position, rotation,
      terminalA, terminalB, terminalOut,
      nodeNames: el.type === "mosfet"
        ? [el.node_a, el.node_b, el.node_g ?? "0"]
        : [el.node_a, el.node_b, ...(el.node_out ? [el.node_out] : [])],
      value: el.value, sourceWaveform: el.source_waveform as CircuitElement["sourceWaveform"],
      acAmplitude: el.ac_amplitude ?? undefined, acPhase: el.ac_phase,
      dcValue: el.dc_value ?? undefined,
      sineFrequency: el.sine_frequency ?? undefined, pulsePeriod: el.pulse_period ?? undefined,
      pulseWidth: el.pulse_width ?? undefined,
      sineAmplitude: el.sine_amplitude ?? undefined,
      sinePhase: el.sine_phase ?? undefined,
      sineOffset: el.sine_offset ?? undefined,
      sineDelay: el.sine_delay ?? undefined,
      sineDamping: el.sine_damping ?? undefined,
      pulseLow: el.pulse_low ?? undefined,
      pulseDelay: el.pulse_delay ?? undefined,
      pulseRise: el.pulse_rise ?? undefined,
      pulseFall: el.pulse_fall ?? undefined,
      openLoopGain: el.open_loop_gain, gainBandwidth: el.gain_bandwidth,
      inputResistance: el.input_resistance, outputResistance: el.output_resistance,
      outputMin: el.output_min, outputMax: el.output_max,
      slewRate: el.slew_rate, inputOffset: el.input_offset,
      mosType: el.mos_type, mosVto: el.mos_vto, mosKp: el.mos_kp,
      mosLambda: el.mos_lambda, mosCgs: el.mos_cgs, mosCgd: el.mos_cgd,
      diodeIs: el.diode_is, diodeN: el.diode_n,
    };
  }
  const s = parsed.request.settings;
  const settings: SimulationSettings = s.mode === "dc" ? { mode: "dc" }
    : s.mode === "ac" ? { mode: "ac", fStart: s.f_start as number, fStop: s.f_stop as number,
      pointsPerDecade: s.points_per_decade as number, sweepType: s.sweep_type as "log" | "linear" }
    : { mode: "transient", tStart: s.t_start as number, tStop: s.t_stop as number,
      tStep: s.t_step as number, method: s.method as "euler" | "trapezoidal" };
  return { title: parsed.title, elements, wires: {}, groundElementId: null, settings };
}

export async function parseSpice(text: string) {
  return spiceToCanvas(await post<ParsedSpiceDTO>("/spice/parse", { text }));
}

export async function exportSpice(request: SimulateRequest, title = "Circuit Simulator"): Promise<string> {
  return (await post<{ text: string }>("/spice/export", { request, title })).text;
}
