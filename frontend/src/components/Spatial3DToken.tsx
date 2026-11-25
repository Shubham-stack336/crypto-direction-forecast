import { useState } from "react";

interface Props {
  symbol: string;
}

export function Spatial3DToken({ symbol }: Props) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const s = symbol.toUpperCase();
  const isEth = s.includes("ETH");
  const isBtc = s.includes("BTC");
  const isSol = s.includes("SOL");
  const isDoge = s.includes("DOGE");
  const isAda = s.includes("ADA");
  const isXrp = s.includes("XRP");

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({ x: -(y * 25), y: x * 25 });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  let symbolGlyph = "◈";
  let glowColor = "rgba(56, 189, 248, 0.45)";
  let bgGradient = "linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)";

  if (isBtc) {
    symbolGlyph = "₿";
    glowColor = "rgba(245, 158, 11, 0.45)";
    bgGradient = "linear-gradient(135deg, #f59e0b 0%, #d97706 60%, #b45309 100%)";
  } else if (isEth) {
    symbolGlyph = "Ξ";
    glowColor = "rgba(99, 102, 241, 0.45)";
    bgGradient = "linear-gradient(135deg, #6366f1 0%, #8b5cf6 60%, #4f46e5 100%)";
  } else if (isSol) {
    symbolGlyph = "◎";
    glowColor = "rgba(20, 241, 149, 0.45)";
    bgGradient = "linear-gradient(135deg, #14F195 0%, #9945FF 100%)";
  } else if (isDoge) {
    symbolGlyph = "Ð";
    glowColor = "rgba(234, 179, 8, 0.45)";
    bgGradient = "linear-gradient(135deg, #eab308 0%, #ca8a04 100%)";
  } else if (isAda) {
    symbolGlyph = "₳";
    glowColor = "rgba(59, 130, 246, 0.45)";
    bgGradient = "linear-gradient(135deg, #2563eb 0%, #0284c7 100%)";
  } else if (isXrp) {
    symbolGlyph = "✕";
    glowColor = "rgba(148, 163, 184, 0.45)";
    bgGradient = "linear-gradient(135deg, #334155 0%, #64748b 100%)";
  }

  return (
    <div
      className="spatial-token-container"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      aria-hidden="true"
    >
      <div
        className="spatial-token"
        style={{
          transform: `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
          boxShadow: `0 20px 40px ${glowColor}, 0 0 80px ${glowColor}`,
        }}
      >
        <div className="token-face token-front" style={{ background: bgGradient }}>
          <div className="token-inner-ring">
            <span className="token-glyph">{symbolGlyph}</span>
          </div>
          <div className="token-shine" />
        </div>
      </div>
      <div className="token-shadow" />
    </div>
  );
}
