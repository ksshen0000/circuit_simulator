import React, { useRef, useState, useCallback, useEffect } from "react";
import { useCircuitStore } from "../../store/circuitStore";
import { useUIStore } from "../../store/uiStore";
import { useSimulationStore } from "../../store/simulationStore";
import { ElementRenderer } from "../Elements/ElementRenderer";
import {
  elementTerminals, GRID_SIZE, type GridPoint, type Point, screenToGrid, gridToScreen, gpKey, gpEqual,
  type CircuitElement, type CircuitNode, mosfetTerminals,
} from "../../types/circuit";
import type { WaveformSignal } from "../../types/simulation";
import { findJunctions } from "../../utils/graphUtils";
import { formatNodeVoltage, nodeValueAt, sampleIndex } from "../../utils/display";

interface WireDrawState {
  active: boolean;
  start: GridPoint | null;
  current: GridPoint | null;
  horizontal: boolean; // horizontal-first L-shape
}

export function CircuitCanvas() {
  const svgRef = useRef<SVGSVGElement>(null);
  const { elements, wires, nodes, addElement, moveElement, addWire, deleteWire,
    setSelected, clearSelected, selectedIds, deleteSelected } = useCircuitStore();
  const { toolMode, pendingType, zoom, pan, setTool, setZoom, applyPanDelta, showGrid } = useUIStore();
  const { result, signals, cursorIndex } = useSimulationStore();

  const [wireDraw, setWireDraw] = useState<WireDrawState>({
    active: false, start: null, current: null, horizontal: true,
  });
  const [dragEl, setDragEl] = useState<{ id: string; startMouse: Point; startPos: GridPoint } | null>(null);
  const [panDrag, setPanDrag] = useState<{ startMouse: Point; startPan: Point } | null>(null);
  const [ghostPos, setGhostPos] = useState<GridPoint | null>(null);

  const svgPoint = useCallback((e: React.MouseEvent): Point => {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const toGrid = useCallback((e: React.MouseEvent): GridPoint => {
    return screenToGrid(svgPoint(e), pan, zoom);
  }, [pan, zoom, svgPoint]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true], [role=dialog]")) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        if (document.activeElement?.tagName === "INPUT") return;
        deleteSelected();
      }
      if (e.key === "Escape") {
        setWireDraw({ active: false, start: null, current: null, horizontal: true });
        setTool("select");
      }
      if (e.key === "r" || e.key === "R") {
        const { rotateElement } = useCircuitStore.getState();
        selectedIds.forEach((id) => rotateElement(id));
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        if (e.shiftKey) useCircuitStore.getState().redo();
        else useCircuitStore.getState().undo();
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === "y" || e.key === "Y")) {
        e.preventDefault();
        useCircuitStore.getState().redo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedIds, deleteSelected, setTool]);

  // Wheel zoom
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom(zoom * factor);
  }, [zoom, setZoom]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    const gp = toGrid(e);

    if (toolMode === "place") setGhostPos(gp);

    if (wireDraw.active) {
      setWireDraw((s) => ({ ...s, current: gp }));
    }

    if (dragEl) {
      const mp = svgPoint(e);
      const dx = mp.x - dragEl.startMouse.x;
      const dy = mp.y - dragEl.startMouse.y;
      const newCenter: GridPoint = {
        gx: dragEl.startPos.gx + Math.round(dx / (GRID_SIZE * zoom)),
        gy: dragEl.startPos.gy + Math.round(dy / (GRID_SIZE * zoom)),
      };
      moveElement(dragEl.id, newCenter);
    }

    if (panDrag) {
      const mp = svgPoint(e);
      applyPanDelta(mp.x - panDrag.startMouse.x, mp.y - panDrag.startMouse.y);
      setPanDrag({ startMouse: mp, startPan: pan });
    }
  }, [toolMode, wireDraw.active, dragEl, panDrag, toGrid, svgPoint, zoom, pan, moveElement, applyPanDelta]);

  const wireActive = wireDraw.active;
  const wireStart = wireDraw.start;
  const wireCurrent = wireDraw.current;
  const wireHorizontal = wireDraw.horizontal;

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0 && e.button !== 1) return;
    const gp = toGrid(e);

    if (toolMode === "pan" || e.button === 1) {
      setPanDrag({ startMouse: svgPoint(e), startPan: pan });
      return;
    }

    if (toolMode === "place" && pendingType) {
      addElement(pendingType, gp);
      if (e.shiftKey) return; // keep placing
      setTool("select");
      return;
    }

    if (toolMode === "wire") {
      if (!wireActive) {
        setWireDraw({ active: true, start: gp, current: gp, horizontal: true });
      } else {
        // Finalize wire
        const pts = lShapedPath(wireStart!, wireCurrent!, wireHorizontal);
        if (pts.length >= 2) addWire(pts);
        setWireDraw({ active: false, start: null, current: null, horizontal: true });
      }
      return;
    }

    clearSelected();
  }, [toolMode, pendingType, wireActive, wireStart, wireCurrent, wireHorizontal,
    pan, toGrid, svgPoint, addElement, addWire, clearSelected, setTool]);

  const onMouseUp = useCallback(() => {
    setDragEl(null);
    setPanDrag(null);
  }, []);

  const onElementClick = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (toolMode !== "select") return;
    if (e.ctrlKey || e.metaKey) {
      const newSet = new Set(selectedIds);
      if (newSet.has(id)) newSet.delete(id); else newSet.add(id);
      setSelected([...newSet]);
    } else {
      setSelected([id]);
    }
  }, [toolMode, selectedIds, setSelected]);

  const onElementMouseDown = useCallback((id: string, e: React.MouseEvent) => {
    if (toolMode !== "select") return;
    e.stopPropagation();
    const el = elements[id];
    if (!el) return;
    setDragEl({ id, startMouse: svgPoint(e), startPos: el.position });
    if (!selectedIds.has(id)) setSelected([id]);
  }, [toolMode, elements, selectedIds, setSelected, svgPoint]);

  const lPath = wireDraw.active && wireDraw.start && wireDraw.current
    ? lShapedPath(wireDraw.start, wireDraw.current, wireDraw.horizontal)
    : null;

  const junctions = findJunctions(wires, elements);

  return (
    <svg
      ref={svgRef}
      style={{ width: "100%", height: "100%", background: "#f8fafc", cursor: getCursor(toolMode) }}
      onMouseMove={onMouseMove}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      onWheel={onWheel}
    >
      {/* Grid */}
      {showGrid && <GridLayer pan={pan} zoom={zoom} />}

      {/* Wires */}
      <g id="layer-wires">
        {Object.values(wires).map((wire) => {
          const pts = wire.points.map((p) => gridToScreen(p, pan, zoom));
          const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
          return (
            <path
              key={wire.id}
              d={d}
              fill="none"
              stroke="#1e293b"
              strokeWidth={2}
              style={{ cursor: "pointer" }}
              onClick={(e) => { e.stopPropagation(); deleteWire(wire.id); }}
            />
          );
        })}
      </g>

      {/* Junction dots */}
      <g id="layer-nodes">
        {junctions.map((jp) => {
          const sp = gridToScreen(jp, pan, zoom);
          return <circle key={gpKey(jp)} cx={sp.x} cy={sp.y} r={4} fill="#1e293b" />;
        })}
      </g>

      {/* Node voltage labels: DC uses the operating point, AC the selected
          frequency (or the first point), transient the cursor (or last point). */}
      {result && (() => {
        const index = sampleIndex(result, cursorIndex);
        return Object.keys(result.nodeVoltages).map((nodeId) => {
          const node = nodes[nodeId];
          if (!node || node.gridPoints.length === 0) return null;
          const gp = node.gridPoints[0];
          const sp = gridToScreen(gp, pan, zoom);
          return (
            <text key={nodeId} x={sp.x + 6} y={sp.y - 6} fontSize={10} fill="#3b82f6" style={{ userSelect: "none" }}>
              {formatNodeVoltage(nodeValueAt(result, nodeId, index))}
            </text>
          );
        });
      })()}

      {/* Components */}
      <g id="layer-components">
        {Object.values(elements).map((el) => (
          <ElementRenderer
            key={el.id}
            element={el}
            pan={pan}
            zoom={zoom}
            selected={selectedIds.has(el.id)}
            onClick={onElementClick}
            onMouseDown={onElementMouseDown}
          />
        ))}
      </g>

      {/* Wire preview */}
      {lPath && (
        <path
          d={lPath.map((p, i) => {
            const sp = gridToScreen(p, pan, zoom);
            return `${i === 0 ? "M" : "L"} ${sp.x} ${sp.y}`;
          }).join(" ")}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={2}
          strokeDasharray="6,3"
          pointerEvents="none"
        />
      )}

      {/* Signal annotations */}
      <SignalAnnotationLayer
        signals={signals}
        elements={elements}
        nodes={nodes}
        pan={pan}
        zoom={zoom}
      />

      {/* Ghost component when placing */}
      {toolMode === "place" && ghostPos && pendingType && (
        <g opacity={0.4} pointerEvents="none">
          <ElementRenderer
            element={{
              id: "__ghost__",
              type: pendingType,
              position: ghostPos,
              rotation: 0,
              ...(pendingType === "mosfet"
                ? (() => {
                  const [terminalA, terminalB, terminalOut] = mosfetTerminals(ghostPos, 0);
                  return { terminalA, terminalB, terminalOut };
                })()
                : {
                  terminalA: { gx: ghostPos.gx - 2, gy: ghostPos.gy },
                  terminalB: { gx: ghostPos.gx + 2, gy: ghostPos.gy },
                }),
              value: 0,
              label: "",
              sourceWaveform: "dc",
              acPhase: 0,
            }}
            pan={pan}
            zoom={zoom}
            selected={false}
            onClick={() => {}}
            onMouseDown={() => {}}
          />
        </g>
      )}
    </svg>
  );
}

function GridLayer({ pan, zoom }: { pan: Point; zoom: number }) {
  const spacing = GRID_SIZE * zoom;
  const offsetX = pan.x % spacing;
  const offsetY = pan.y % spacing;
  return (
    <g>
      <defs>
        <pattern id="grid" x={offsetX} y={offsetY} width={spacing} height={spacing} patternUnits="userSpaceOnUse">
          <circle cx={0} cy={0} r={1} fill="#cbd5e1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)" />
    </g>
  );
}

function lShapedPath(start: GridPoint, end: GridPoint, horizontal: boolean): GridPoint[] {
  if (gpEqual(start, end)) return [start];
  if (horizontal) {
    const mid: GridPoint = { gx: end.gx, gy: start.gy };
    return [start, mid, end];
  } else {
    const mid: GridPoint = { gx: start.gx, gy: end.gy };
    return [start, mid, end];
  }
}

function getCursor(tool: string): string {
  if (tool === "wire") return "crosshair";
  if (tool === "place") return "copy";
  if (tool === "pan") return "grab";
  return "default";
}

function nodeRepresentativePoint(
  nodeId: string,
  nodes: Record<string, CircuitNode>,
  elements: Record<string, CircuitElement>,
): GridPoint | null {
  const node = nodes[nodeId];
  if (!node || node.gridPoints.length === 0) return null;
  for (const el of Object.values(elements)) {
    if (el.type === "ground") continue;
    for (const term of elementTerminals(el)) {
      if (node.gridPoints.some((gp) => gp.gx === term.gx && gp.gy === term.gy)) {
        return term;
      }
    }
  }
  return node.gridPoints[0];
}

interface AnnotationLayerProps {
  signals: WaveformSignal[];
  elements: Record<string, CircuitElement>;
  nodes: Record<string, CircuitNode>;
  pan: Point;
  zoom: number;
}

function SignalAnnotationLayer({ signals, elements, nodes, pan, zoom }: AnnotationLayerProps) {
  if (signals.length === 0) return null;
  const r = GRID_SIZE * zoom * 0.9;

  return (
    <g id="layer-annotations" pointerEvents="none">
      {signals.map((sig) => {
        if (sig.key.startsWith("V(")) {
          const nodeId = sig.key.slice(2, -1);
          const gp = nodeRepresentativePoint(nodeId, nodes, elements);
          if (!gp) return null;
          const sp = gridToScreen(gp, pan, zoom);
          return (
            <g key={sig.key}>
              <circle cx={sp.x} cy={sp.y} r={r} fill={sig.color + "22"} stroke={sig.color} strokeWidth={2} strokeDasharray="4 2" />
              <text x={sp.x} y={sp.y - r - 4} textAnchor="middle" fontSize={10} fontWeight="bold" fill={sig.color} style={{ userSelect: "none" }}>
                {sig.key}
              </text>
            </g>
          );
        } else if (sig.key.startsWith("I(")) {
          const label = sig.key.slice(2, -1);
          const el = Object.values(elements).find((e) => e.label === label);
          if (!el) return null;
          const sp = gridToScreen(el.position, pan, zoom);
          return (
            <g key={sig.key}>
              <circle cx={sp.x} cy={sp.y} r={r * 1.6} fill="none" stroke={sig.color} strokeWidth={2} strokeDasharray="4 2" />
              <text x={sp.x} y={sp.y - r * 1.6 - 4} textAnchor="middle" fontSize={10} fontWeight="bold" fill={sig.color} style={{ userSelect: "none" }}>
                {sig.key}
              </text>
            </g>
          );
        }
        return null;
      })}
    </g>
  );
}
