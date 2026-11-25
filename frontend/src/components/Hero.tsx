import { lazy, Suspense, useCallback, useState } from "react";

import { LogoMark } from "./Logo";

const HeroScene = lazy(() => import("./HeroScene"));
const canRender3D = typeof window !== "undefined" && "WebGL2RenderingContext" in window;

export function Hero({ coinCount }: { coinCount: number | null }) {
  const [failed, setFailed] = useState(!canRender3D);
  const onFail = useCallback(() => setFailed(true), []);
  const fallback = (
    <div className="hero-fallback">
      <LogoMark size={220} />
    </div>
  );

  return (
    <header className="hero" id="top">
      <div className="hero-copy">
        <h1>Which way will crypto move next?</h1>
        <p className="subtitle">
          UP, DOWN or SIDEWAYS over the next three hours, for{" "}
          {coinCount === null ? "every major USDT pair" : `${coinCount} coins`}. Live Binance candles, honest
          probabilities, and a track record you can check.
        </p>
        <div className="hero-actions">
          <a className="button" href="#dashboard">
            Open the dashboard
          </a>
          <a className="button secondary" href="#scanner">
            Scan the market
          </a>
        </div>
      </div>
      <div className="hero-stage" aria-hidden="true">
        {failed ? fallback : (
          <Suspense fallback={fallback}>
            <HeroScene onFail={onFail} />
          </Suspense>
        )}
      </div>
    </header>
  );
}
