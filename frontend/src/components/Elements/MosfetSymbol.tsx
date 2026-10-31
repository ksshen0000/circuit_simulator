export function MosfetSymbol() {
  return <g fill="none" stroke="currentColor" strokeWidth={2}>
    {/* gate lead and plate */}
    <path d="M -40 0 H -24 M -24 -26 V 26" />
    {/* channel */}
    <path d="M -16 -26 V -10 M -16 -6 V 6 M -16 10 V 26" strokeWidth={3} />
    {/* drain (top right) and source (bottom right) */}
    <path d="M -16 -18 H 24 V -40 M -16 18 H 24 V 40" />
    {/* body arrow pointing into the channel for an NMOS */}
    <path d="M -16 0 H -4" />
    <path d="M -10 -4 L -4 0 L -10 4" fill="currentColor" stroke="none" />
    <circle cx={-40} cy={0} r={2.5} fill="white" />
    <circle cx={40} cy={-40} r={2.5} fill="white" />
    <circle cx={40} cy={40} r={2.5} fill="white" />
  </g>;
}
