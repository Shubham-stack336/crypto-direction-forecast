/** Project mark: a block (hexagon) holding the three answers the model can give: up, sideways, down. */
export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
  <path d="M32 3 57 17.5v29L32 61 7 46.5v-29Z" fill="rgba(125,240,200,.08)" stroke="#7df0c8" strokeWidth="2.5" strokeLinejoin="round" />
  <path d="M20 26 32 13l12 13" fill="none" stroke="#4ade9f" strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round" />
  <path d="M20 32h24" fill="none" stroke="#f5c35b" strokeWidth="5.5" strokeLinecap="round" />
  <path d="M20 38l12 13 12-13" fill="none" stroke="#ff7a70" strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="logo">
      <LogoMark />
      <span>Crypto Direction</span>
    </span>
  );
}
