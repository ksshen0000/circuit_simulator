import {
  type CircuitElement, type ComponentType, type GridPoint, type Rotation, type Wire,
  opampTerminals, terminalPositions,
} from "../types/circuit";

export const CIRCUIT_TEMPLATES = [
  { id: "noninverting", name: "同相放大器 ×10", description: "输入 0.1 V，预期输出约 +1 V；反馈电阻 9 kΩ / 1 kΩ。" },
  { id: "inverting", name: "反相放大器 ×10", description: "输入 0.1 V，预期输出约 −1 V；输入电阻 1 kΩ，反馈电阻 10 kΩ。" },
  { id: "follower", name: "电压跟随器", description: "输入 0.1 V，预期输出约 0.1 V；输出直接反馈到反相端。" },
] as const;

export type CircuitTemplateId = typeof CIRCUIT_TEMPLATES[number]["id"];

/** Fresh editable circuit data, using the same schema as saved circuits. */
export function createCircuitTemplate(id: CircuitTemplateId) {
  const elements: Record<string, CircuitElement> = {};
  const wires: Record<string, Wire> = {};
  const add = (type: ComponentType, label: string, gx: number, gy: number, value = 0, rotation: Rotation = 0) => {
    const position = { gx, gy };
    const [terminalA, terminalB, terminalOut] = type === "ground" ? [position, position]
      : type === "opamp" ? opampTerminals(position, rotation) : terminalPositions(position, rotation);
    elements[label] = {
      id: label, type, label, position, rotation, terminalA, terminalB, terminalOut,
      value, sourceWaveform: "dc", acPhase: 0,
      ...(type === "opamp" ? {
        openLoopGain: 1e5, gainBandwidth: 1e6, inputResistance: 1e9,
        outputResistance: 75, outputMin: -13.5, outputMax: 13.5,
        slewRate: 5e5, inputOffset: 0,
      } : {}),
      ...(type === "voltage_source" ? { acAmplitude: 1, sineFrequency: 1000 } : {}),
    };
  };
  const wire = (...points: [number, number][]) => {
    const key = `W${Object.keys(wires).length + 1}`;
    wires[key] = { id: key, points: points.map(([gx, gy]): GridPoint => ({ gx, gy })) };
  };

  add("voltage_source", "V1", 4, 6, 0.1, 90);
  add("ground", "GND1", 4, 9);
  wire([4, 8], [4, 9]);
  add("opamp", "U1", 14, 5);
  add("resistor", "RL", 26, 8, 10000, 90);
  add("ground", "GND2", 26, 12);
  wire([16, 5], [26, 5], [26, 6]);
  wire([26, 10], [26, 12]);

  if (id === "follower") {
    wire([4, 4], [12, 4]);
    wire([12, 6], [12, 10], [22, 10], [22, 5]);
  } else {
    add("resistor", "R1", 17, 10, id === "inverting" ? 10000 : 9000);
    wire([12, 6], [12, 10], [15, 10]);
    wire([19, 10], [22, 10], [22, 5]);
    if (id === "noninverting") {
      wire([4, 4], [12, 4]);
      add("resistor", "R2", 12, 14, 1000, 90);
      add("ground", "GND3", 12, 17);
      wire([12, 10], [12, 12]);
      wire([12, 16], [12, 17]);
    } else {
      add("resistor", "R2", 8, 4, 1000);
      wire([4, 4], [6, 4]);
      wire([10, 4], [10, 6], [12, 6]);
      add("ground", "GND3", 8, 1);
      wire([8, 1], [12, 1], [12, 4]);
    }
  }
  return { elements, wires, groundElementId: "GND1" };
}
