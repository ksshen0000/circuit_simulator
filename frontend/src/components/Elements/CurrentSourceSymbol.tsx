export function CurrentSourceSymbol() {
  return (
    <g>
      <line x1={-40} y1={0} x2={-20} y2={0} stroke="currentColor" strokeWidth={2} />
      <circle cx={0} cy={0} r={20} fill="none" stroke="currentColor" strokeWidth={2} />
      {/* Current flows from terminal A (left) to terminal B (right) */}
      <line x1={-10} y1={0} x2={10} y2={0} stroke="currentColor" strokeWidth={1.5} />
      <polygon points="6,-4 14,0 6,4" fill="currentColor" />
      <line x1={20} y1={0} x2={40} y2={0} stroke="currentColor" strokeWidth={2} />
    </g>
  );
}
