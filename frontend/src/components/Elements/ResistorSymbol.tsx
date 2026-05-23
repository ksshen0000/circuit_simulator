export function ResistorSymbol() {
  const w = 28, h = 12;
  return (
    <g>
      <line x1={-40} y1={0} x2={-w} y2={0} stroke="currentColor" strokeWidth={2} />
      <rect x={-w} y={-h / 2} width={2 * w} height={h} fill="none" stroke="currentColor" strokeWidth={2} rx={1} />
      <line x1={w} y1={0} x2={40} y2={0} stroke="currentColor" strokeWidth={2} />
    </g>
  );
}
