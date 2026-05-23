export function GroundSymbol() {
  // Connection point is at origin (0,0). Bars extend downward.
  return (
    <g>
      <line x1={-20} y1={0} x2={20} y2={0} stroke="currentColor" strokeWidth={2.5} />
      <line x1={-13} y1={9} x2={13} y2={9} stroke="currentColor" strokeWidth={2} />
      <line x1={-6} y1={18} x2={6} y2={18} stroke="currentColor" strokeWidth={1.5} />
    </g>
  );
}
