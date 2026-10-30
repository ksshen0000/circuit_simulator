import React, { memo } from "react";
import { elementTerminals, GRID_SIZE, type CircuitElement, type Point } from "../../types/circuit";
import { ResistorSymbol } from "./ResistorSymbol";
import { CapacitorSymbol } from "./CapacitorSymbol";
import { InductorSymbol } from "./InductorSymbol";
import { VoltageSourceSymbol } from "./VoltageSourceSymbol";
import { CurrentSourceSymbol } from "./CurrentSourceSymbol";
import { OpampSymbol } from "./OpampSymbol";
import { GroundSymbol } from "./GroundSymbol";

interface Props {
  element: CircuitElement;
  pan: Point;
  zoom: number;
  selected: boolean;
  onClick: (id: string, e: React.MouseEvent) => void;
  onMouseDown: (id: string, e: React.MouseEvent) => void;
}

const SYMBOL_MAP: Record<string, React.ComponentType<{ isAC?: boolean }>> = {
  resistor: ResistorSymbol,
  capacitor: CapacitorSymbol,
  inductor: InductorSymbol,
  voltage_source: VoltageSourceSymbol,
  current_source: CurrentSourceSymbol,
  ground: GroundSymbol,
  opamp: OpampSymbol,
};

export const ElementRenderer = memo(function ElementRenderer({
  element, pan, zoom, selected, onClick, onMouseDown,
}: Props) {
  const cx = element.position.gx * GRID_SIZE * zoom + pan.x;
  const cy = element.position.gy * GRID_SIZE * zoom + pan.y;

  const Symbol = SYMBOL_MAP[element.type];
  if (!Symbol) return null;


  return (
    <g
      transform={`translate(${cx},${cy}) rotate(${element.rotation}) scale(${zoom})`}
      style={{ cursor: "pointer", color: selected ? "#3b82f6" : "#1e293b" }}
      onClick={(e) => onClick(element.id, e)}
      onMouseDown={(e) => onMouseDown(element.id, e)}
    >
      {selected && (
        <rect
          x={-45} y={-25} width={90} height={50}
          fill="rgba(59,130,246,0.1)"
          stroke="#3b82f6"
          strokeWidth={1 / zoom}
          strokeDasharray={`${4 / zoom},${2 / zoom}`}
          rx={3}
        />
      )}
      <Symbol isAC={element.sourceWaveform === "sine"} />
      {element.nodeNames && elementTerminals(element).map((pin, i) => {
        const dx = (pin.gx - element.position.gx) * GRID_SIZE;
        const dy = (pin.gy - element.position.gy) * GRID_SIZE;
        const angle = -element.rotation * Math.PI / 180;
        const x = dx * Math.cos(angle) - dy * Math.sin(angle);
        const y = dx * Math.sin(angle) + dy * Math.cos(angle);
        return <g key={i}>
          <circle cx={x} cy={y} r={3} fill="#fff" stroke="currentColor" />
          <text x={x + (x < 0 ? -5 : 5)} y={y + 4} textAnchor={x < 0 ? "end" : "start"}
            fontSize={10} fill="#0369a1" stroke="none">{element.nodeNames?.[i]}</text>
        </g>;
      })}
      {/* Label */}
      <text
        x={0} y={element.type === "ground" ? 32 : -28}
        textAnchor="middle"
        fontSize={11 / zoom * zoom}
        fill="#64748b"
        style={{ userSelect: "none", fontSize: 11 }}
        transform={`rotate(${-element.rotation})`}
      >
        {element.label}
      </text>
      {/* Value */}
      <text
        x={0} y={element.type === "ground" ? 44 : -16}
        textAnchor="middle"
        fontSize={9}
        fill="#94a3b8"
        style={{ userSelect: "none" }}
        transform={`rotate(${-element.rotation})`}
      >
        {formatValue(element)}
      </text>
    </g>
  );
});

function formatValue(el: CircuitElement): string {
  const v = el.value;
  if (el.type === "resistor") return formatSI(v, "Ω");
  if (el.type === "capacitor") return formatSI(v, "F");
  if (el.type === "inductor") return formatSI(v, "H");
  if (el.type === "voltage_source") return `${v}V`;
  if (el.type === "current_source") return formatSI(v, "A");
  return "";
}

function formatSI(v: number, unit: string): string {
  if (v >= 1e9) return `${(v / 1e9).toPrecision(3)}G${unit}`;
  if (v >= 1e6) return `${(v / 1e6).toPrecision(3)}M${unit}`;
  if (v >= 1e3) return `${(v / 1e3).toPrecision(3)}k${unit}`;
  if (v >= 1) return `${v.toPrecision(3)}${unit}`;
  if (v >= 1e-3) return `${(v * 1e3).toPrecision(3)}m${unit}`;
  if (v >= 1e-6) return `${(v * 1e6).toPrecision(3)}μ${unit}`;
  if (v >= 1e-9) return `${(v * 1e9).toPrecision(3)}n${unit}`;
  return `${(v * 1e12).toPrecision(3)}p${unit}`;
}
