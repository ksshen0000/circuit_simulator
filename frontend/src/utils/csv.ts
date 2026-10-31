import type { SimulationResult } from "../types/simulation";

function quote(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** CSV export of the full result, independent of which signals are visible. */
export function resultToCsv(result: SimulationResult): string {
  const nodes = Object.keys(result.nodeVoltages);
  const branches = Object.keys(result.branchCurrents);
  const ac = result.mode === "ac";
  const header = ["x"];
  if (ac) {
    for (const node of nodes) header.push(`V(${node})_mag`, `V(${node})_phase`);
    for (const branch of branches) header.push(`I(${branch})_mag`, `I(${branch})_phase`);
  } else {
    for (const node of nodes) header.push(`V(${node})`);
    for (const branch of branches) header.push(`I(${branch})`);
  }
  const rows = result.xValues.map((x, index) => {
    const row: (number | string)[] = [x];
    for (const node of nodes) {
      row.push(ac
        ? result.nodeVoltagesMag?.[node]?.[index] ?? 0
        : result.nodeVoltages[node]?.[index] ?? 0);
      if (ac) row.push(result.nodeVoltagesPhase?.[node]?.[index] ?? 0);
    }
    for (const branch of branches) {
      row.push(ac
        ? result.branchCurrentsMag?.[branch]?.[index] ?? 0
        : result.branchCurrents[branch]?.[index] ?? 0);
      if (ac) row.push(result.branchCurrentsPhase?.[branch]?.[index] ?? 0);
    }
    return row;
  });
  return [header, ...rows]
    .map((row) => row.map((value) => quote(String(value))).join(","))
    .join("\n") + "\n";
}

export function downloadText(filename: string, text: string, type = "text/plain;charset=utf-8"): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
