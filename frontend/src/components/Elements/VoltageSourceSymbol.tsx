export function VoltageSourceSymbol({ isAC }: { isAC?: boolean }) {
  return (
    <g>
      <line x1={-40} y1={0} x2={-20} y2={0} stroke="currentColor" strokeWidth={2} />
      <circle cx={0} cy={0} r={20} fill="none" stroke="currentColor" strokeWidth={2} />
      {isAC ? (
        <path d="M -10 4 Q -5 -8 0 0 Q 5 8 10 -4" fill="none" stroke="currentColor" strokeWidth={1.5} />
      ) : (
        <>
          <text x={0} y={-6} textAnchor="middle" fontSize={14} fill="currentColor" fontWeight="bold">+</text>
          <text x={0} y={12} textAnchor="middle" fontSize={14} fill="currentColor" fontWeight="bold">−</text>
        </>
      )}
      <line x1={20} y1={0} x2={40} y2={0} stroke="currentColor" strokeWidth={2} />
    </g>
  );
}
