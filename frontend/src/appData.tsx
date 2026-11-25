import { createContext, useContext, useEffect, type ReactNode } from "react";

import { useAlerts } from "./alerts";
import { getCoins, getLive, getReady } from "./api/client";
import { useAsync } from "./api/useAsync";
import { useWatchlist } from "./useWatchlist";

export const REFRESH_MS = 60_000;

/** Calls `action` every minute while the tab is visible. */
export function useEveryMinute(action: () => void) {
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") action();
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [action]);
}

function useAppDataValue() {
  const live = useAsync((signal) => getLive(signal), []);
  const ready = useAsync((signal) => getReady(signal), []);
  const coins = useAsync((signal) => getCoins(signal), []);
  useEveryMinute(coins.refresh);
  const [watchlist, toggleWatch] = useWatchlist();
  const alerts = useAlerts(coins.state.status === "success" ? coins.state.data : null);
  return { live, ready, coins, watchlist, toggleWatch, alerts };
}

const Context = createContext<ReturnType<typeof useAppDataValue> | null>(null);

/** Data every page shares, loaded once. */
export function AppDataProvider({ children }: { children: ReactNode }) {
  return <Context.Provider value={useAppDataValue()}>{children}</Context.Provider>;
}

export function useAppData() {
  const value = useContext(Context);
  if (!value) throw new Error("useAppData needs AppDataProvider");
  return value;
}
