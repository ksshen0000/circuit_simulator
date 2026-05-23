export function InductorSymbol() {
  // Three bumps using arcs
  const r = 10;
  const bumps = [-20, 0, 20];
  return (
    <g>
      <line x1={-40} y1={0} x2={-30} y2={0} stroke="currentColor" strokeWidth={2} />
      {bumps.map((cx, i) => (
        <path
          key={i}
          d={`M ${cx - r} 0 A ${r} ${r} 0 0 1 ${cx + r} 0`}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
        />
      ))}
      <line x1={30} y1={0} x2={40} y2={0} stroke="currentColor" strokeWidth={2} />
    </g>
  );
}
