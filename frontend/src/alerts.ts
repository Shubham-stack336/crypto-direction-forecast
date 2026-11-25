import { useCallback, useEffect, useState } from "react";

import type { Coin } from "./api/types";
import { formatPrice, symbolToSlug } from "./format";

export interface PriceAlert {
  id: string;
  slug: string;
  side: "above" | "below";
  price: number;
  firedAt: string | null;
}

const KEY = "price-alerts";
export const MAX_ALERTS = 20;

function valid(value: unknown): value is PriceAlert {
  const a = value as PriceAlert;
  return typeof a?.id === "string" && typeof a.slug === "string" && typeof a.price === "number" &&
    (a.side === "above" || a.side === "below");
}

function read(): PriceAlert[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(value) ? value.filter(valid) : [];
  } catch {
    return [];
  }
}

export const reached = (a: PriceAlert, last: number) => (a.side === "above" ? last >= a.price : last <= a.price);

/** Alerts live in this browser and are checked whenever new prices arrive while the site is open. */
export function useAlerts(coins: Coin[] | null) {
  const [alerts, setAlerts] = useState(read);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(alerts));
    } catch {
      // storage blocked: alerts last until the page is closed
    }
  }, [alerts]);

  useEffect(() => {
    if (!coins) return;
    const price = new Map(coins.map((c) => [symbolToSlug(c.symbol), c.last]));
    const hit = alerts.filter((a) => !a.firedAt && price.has(a.slug) && reached(a, price.get(a.slug)!));
    if (hit.length === 0) return;
    const ids = new Set(hit.map((a) => a.id));
    const now = new Date().toISOString();
    setAlerts((list) => list.map((a) => (ids.has(a.id) ? { ...a, firedAt: now } : a)));
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      for (const a of hit) {
        try {
          new Notification(`${a.slug.split("-")[0]} is ${a.side} ${formatPrice(a.price)}`);
        } catch {
          // some phones only allow notifications from a service worker; the page still shows the alert
        }
      }
    }
  }, [coins, alerts]);

  const add = useCallback((slug: string, side: PriceAlert["side"], price: number) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setAlerts((list) => [{ id, slug, side, price, firedAt: null }, ...list].slice(0, MAX_ALERTS));
  }, []);
  const remove = useCallback((id: string) => setAlerts((list) => list.filter((a) => a.id !== id)), []);
  return { alerts, add, remove };
}
