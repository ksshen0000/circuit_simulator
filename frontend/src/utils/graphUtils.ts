import { elementTerminals, type CircuitElement, type CircuitNode, type Wire, gpKey, type GridPoint } from "../types/circuit";

class UnionFind {
  private parent: Map<string, string> = new Map();

  find(key: string): string {
    if (!this.parent.has(key)) this.parent.set(key, key);
    const p = this.parent.get(key)!;
    if (p !== key) {
      const root = this.find(p);
      this.parent.set(key, root);
      return root;
    }
    return key;
  }

  union(a: string, b: string): void {
    const ra = this.find(a);
    const rb = this.find(b);
    if (ra !== rb) this.parent.set(ra, rb);
  }

  groups(): Map<string, string[]> {
    const groups = new Map<string, string[]>();
    for (const key of this.parent.keys()) {
      const root = this.find(key);
      if (!groups.has(root)) groups.set(root, []);
      groups.get(root)!.push(key);
    }
    return groups;
  }
}

export function computeNodes(
  elements: Record<string, CircuitElement>,
  wires: Record<string, Wire>,
  groundElementId: string | null,
): Record<string, CircuitNode> {
  const uf = new UnionFind();

  // Enumerate every grid point along each wire segment and union them.
  // This ensures element terminals that lie anywhere along a wire (not just at
  // the explicit vertices) are correctly merged into the same node.
  const allWireGridKeys = new Set<string>();

  for (const wire of Object.values(wires)) {
    for (let i = 0; i < wire.points.length - 1; i++) {
      const p1 = wire.points[i];
      const p2 = wire.points[i + 1];
      let prevKey: string | null = null;

      if (p1.gx === p2.gx) {
        // Vertical segment
        const minY = Math.min(p1.gy, p2.gy);
        const maxY = Math.max(p1.gy, p2.gy);
        for (let gy = minY; gy <= maxY; gy++) {
          const key = gpKey({ gx: p1.gx, gy });
          uf.find(key);
          allWireGridKeys.add(key);
          if (prevKey !== null) uf.union(prevKey, key);
          prevKey = key;
        }
      } else if (p1.gy === p2.gy) {
        // Horizontal segment
        const minX = Math.min(p1.gx, p2.gx);
        const maxX = Math.max(p1.gx, p2.gx);
        for (let gx = minX; gx <= maxX; gx++) {
          const key = gpKey({ gx, gy: p1.gy });
          uf.find(key);
          allWireGridKeys.add(key);
          if (prevKey !== null) uf.union(prevKey, key);
          prevKey = key;
        }
      }
    }
  }

  // Register all element terminals. If a terminal shares a grid key with a wire
  // point already in the union-find, uf.find() returns the same root automatically.
  for (const el of Object.values(elements)) {
    for (const pin of elementTerminals(el)) uf.find(gpKey(pin));
  }

  // Named nets retain connectivity without requiring crossing auto-routed wires.
  const namedPins = new Map<string, string>();
  for (const el of Object.values(elements)) {
    elementTerminals(el).forEach((pin, i) => {
      const name = el.nodeNames?.[i];
      if (!name) return;
      const key = name === "0" || name.toUpperCase() === "GND" ? "GND" : name.toUpperCase();
      const previous = namedPins.get(key);
      if (previous) uf.union(gpKey(pin), previous);
      else namedPins.set(key, gpKey(pin));
    });
  }
  let groundPin = namedPins.get("GND");
  if (groundElementId && elements[groundElementId]) {
    const pin = gpKey(elements[groundElementId].terminalA);
    if (groundPin) uf.union(pin, groundPin);
    groundPin = pin;
  }
  for (const el of Object.values(elements)) {
    if (el.type !== "ground") continue;
    const pin = gpKey(el.terminalA);
    if (groundPin) uf.union(pin, groundPin);
    else groundPin = pin;
  }
  const groundRoot = groundPin ? uf.find(groundPin) : null;
  const rootNames = new Map<string, string>();
  for (const [name, pin] of namedPins) rootNames.set(uf.find(pin), name);
  const reserved = new Set(namedPins.keys());
  const nodes: Record<string, CircuitNode> = {};
  let nodeCounter = 1;
  for (const [root, keys] of uf.groups()) {
    let id = root === groundRoot ? "GND" : rootNames.get(root);
    if (!id) {
      do { id = `N${nodeCounter++}`; } while (reserved.has(id));
    }
    const gridPoints = keys.map((key): GridPoint => {
      const [gx, gy] = key.split(",").map(Number);
      return { gx, gy };
    });
    nodes[id] = { id, gridPoints };
  }

  return nodes;
}

export function pointToNode(
  p: GridPoint,
  nodes: Record<string, CircuitNode>,
): string | null {
  const key = gpKey(p);
  for (const node of Object.values(nodes)) {
    if (node.gridPoints.some((gp) => gpKey(gp) === key)) return node.id;
  }
  return null;
}

export function findJunctions(
  wires: Record<string, Wire>,
  elements: Record<string, CircuitElement>,
): GridPoint[] {
  const count = new Map<string, number>();

  const inc = (p: GridPoint) => {
    const k = gpKey(p);
    count.set(k, (count.get(k) ?? 0) + 1);
  };

  for (const wire of Object.values(wires)) {
    inc(wire.points[0]);
    inc(wire.points[wire.points.length - 1]);
  }
  for (const el of Object.values(elements)) {
    for (const pin of elementTerminals(el)) inc(pin);
  }

  const junctions: GridPoint[] = [];
  for (const [key, cnt] of count.entries()) {
    if (cnt >= 3) {
      const [gx, gy] = key.split(",").map(Number);
      junctions.push({ gx, gy });
    }
  }
  return junctions;
}
