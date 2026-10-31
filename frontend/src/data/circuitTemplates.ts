import {
  type CircuitElement, type ComponentType, type GridPoint, type Rotation, type Wire,
  mosfetTerminals, opampTerminals, terminalPositions,
} from "../types/circuit";

export const CIRCUIT_TEMPLATES = [
  { id: "noninverting", name: "同相放大器 ×10", description: "输入 0.1 V，预期输出约 +1 V；反馈电阻 9 kΩ / 1 kΩ。" },
  { id: "inverting", name: "反相放大器 ×10", description: "输入 0.1 V，预期输出约 −1 V；输入电阻 1 kΩ，反馈电阻 10 kΩ。" },
  { id: "follower", name: "电压跟随器", description: "输入 0.1 V，预期输出约 0.1 V；输出直接反馈到反相端。" },
  { id: "mosfet-cs", name: "MOSFET 共源放大", description: "NMOS Level-1，栅极偏置 2 V；输出约 4.48 V，可切换到 AC 查看反相增益。" },
] as const;

export type CircuitTemplateId = typeof CIRCUIT_TEMPLATES[number]["id"];

/** Fresh editable circuit data, using the same schema as saved circuits. */
export function createCircuitTemplate(id: CircuitTemplateId) {
  const elements: Record<string, CircuitElement> = {};
  const wires: Record<string, Wire> = {};
  const add = (type: ComponentType, label: string, gx: number, gy: number, value = 0, rotation: Rotation = 0) => {
    const position = { gx, gy };
    const [terminalA, terminalB, terminalOut] = type === "ground" ? [position, position]
      : type === "opamp" ? opampTerminals(position, rotation)
        : type === "mosfet" ? mosfetTerminals(position, rotation)
          : terminalPositions(position, rotation);
    elements[label] = {
      id: label, type, label, position, rotation, terminalA, terminalB, terminalOut,
      value, sourceWaveform: "dc", acPhase: 0,
      ...(type === "opamp" ? {
        openLoopGain: 1e5, gainBandwidth: 1e6, inputResistance: 1e9,
        outputResistance: 75, outputMin: -13.5, outputMax: 13.5,
        slewRate: 5e5, inputOffset: 0,
      } : {}),
      ...(type === "voltage_source" ? { acAmplitude: 1 } : {}),
      ...(type === "mosfet" ? { mosType: "nmos" as const, mosVto: 1, mosKp: 1e-3,
        mosLambda: 0, mosCgs: 0, mosCgd: 0 } : {}),
    };
  };
  const wire = (...points: [number, number][]) => {
    const key = `W${Object.keys(wires).length + 1}`;
    wires[key] = { id: key, points: points.map(([gx, gy]): GridPoint => ({ gx, gy })) };
  };

  if (id === "mosfet-cs") {
    add("voltage_source", "VDD1", 6, 2, 5, 90);
    add("ground", "GND1", 6, 7);
    wire([6, 4], [6, 7]);
    add("resistor", "RD1", 14, 4, 1000, 90);
    wire([6, 0], [14, 0], [14, 2]);
    add("mosfet", "M1", 14, 10);
    if (elements.M1) {
      elements.M1.mosVto = 1;
      elements.M1.mosKp = 1e-3;
      elements.M1.mosLambda = 0.01;
    }
    if (elements.VDD1) elements.VDD1.acAmplitude = 0;
    if (elements.VG1) elements.VG1.acAmplitude = 1;
    wire([14, 6], [14, 8], [16, 8]);
    add("ground", "GND2", 16, 15);
    wire([16, 12], [16, 15]);
    add("voltage_source", "VG1", 4, 10, 2, 90);
    add("ground", "GND3", 4, 15);
    wire([4, 12], [4, 15]);
    wire([4, 8], [12, 8], [12, 10]);
    return { elements, wires, groundElementId: "GND1" };
  }

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
