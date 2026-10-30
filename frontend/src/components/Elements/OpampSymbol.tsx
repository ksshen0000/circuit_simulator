export function OpampSymbol() {
  return <g fill="none" stroke="currentColor" strokeWidth={2}>
    <path d="M -24 -30 L -24 30 L 26 0 Z M -40 -20 H -24 M -40 20 H -24 M 26 0 H 40" />
    <path d="M -19 -18 H -9 M -14 -23 V -13 M -19 18 H -9" strokeWidth={1.5} />
    <circle cx={-40} cy={-20} r={2.5} fill="white" />
    <circle cx={-40} cy={20} r={2.5} fill="white" />
    <circle cx={40} cy={0} r={2.5} fill="white" />
  </g>;
}
