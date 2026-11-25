import { createContext, useContext, type ReactNode } from "react";

import { getCoins, getLive, getReady } from "./api/client";
import { useAsync } from "./api/useAsync";
import { useWatchlist } from "./useWatchlist";

function useAppDataValue() {
  const live = useAsync((signal) => getLive(signal), []);
  const ready = useAsync((signal) => getReady(signal), []);
  const coins = useAsync((signal) => getCoins(signal), []);
  const [watchlist, toggleWatch] = useWatchlist();
  return { live, ready, coins, watchlist, toggleWatch };
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
