import { useState, type FormEvent } from "react";

import { MAX_ALERTS, reached, type PriceAlert } from "../alerts";
import { useAppData } from "../appData";
import { Card, Empty } from "../components/StateViews";
import { formatPrice, formatUtc, symbolToSlug } from "../format";

export default function AlertsPage() {
  const { coins, alerts } = useAppData();
  const list = coins.state.status === "success" ? coins.state.data : [];
  const [slug, setSlug] = useState("BTC-USDT");
  const [side, setSide] = useState<PriceAlert["side"]>("above");
  const [price, setPrice] = useState("");
  const [error, setError] = useState("");
  const [permission, setPermission] = useState(typeof Notification === "undefined" ? "unsupported" : Notification.permission);
  const coin = list.find((c) => symbolToSlug(c.symbol) === slug);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = Number(price);
    if (!(value > 0)) return setError("Enter a price above zero.");
    if (alerts.alerts.length >= MAX_ALERTS) return setError(`You can keep ${MAX_ALERTS} alerts. Remove one first.`);
    if (coin && reached({ id: "", slug, side, price: value, firedAt: null }, coin.last))
      return setError(`The price is already ${side} ${formatPrice(value)}.`);
    alerts.add(slug, side, value);
    setPrice("");
    setError("");
  };

  return (
    <>
      <div className="page-head">
        <h1>Alerts</h1>
        <p>Get told when a price crosses a level. Alerts stay in this browser and are checked once a minute while the site is open.</p>
      </div>
      <div className="grid">
        <Card title="New alert" id="new-alert-title">
          <form className="form" onSubmit={submit}>
            <label>
              Coin
              <select value={slug} onChange={(e) => setSlug(e.target.value)}>
                {Array.from(new Set(["BTC-USDT", ...list.map((c) => symbolToSlug(c.symbol))])).map((s) => (
                  <option key={s} value={s}>{s.split("-")[0]}</option>
                ))}
              </select>
            </label>
            <label>
              When the price is
              <select value={side} onChange={(e) => setSide(e.target.value as PriceAlert["side"])}>
                <option value="above">above</option>
                <option value="below">below</option>
              </select>
            </label>
            <label>
              Price (USDT)
              <input type="number" step="any" min="0" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
            </label>
            {coin && <p className="hint">Now {formatPrice(coin.last)}</p>}
            {error && <p className="state state-error" role="alert">{error}</p>}
            <button type="submit" className="button">Add alert</button>
          </form>
        </Card>
        <Card title="Your alerts" id="alerts-title">
          {permission === "default" && (
            <button type="button" className="button secondary" onClick={async () => setPermission(await Notification.requestPermission())}>
              Turn on browser notifications
            </button>
          )}
          {permission === "denied" && <p className="hint">Notifications are blocked in your browser settings. Alerts still show here.</p>}
          {alerts.alerts.length === 0 ? <Empty>No alerts yet.</Empty> : (
            <ul className="rows">
              {alerts.alerts.map((a) => (
                <li key={a.id}>
                  <span>
                    <strong>{a.slug.split("-")[0]}</strong> {a.side} {formatPrice(a.price)}
                    <small>{a.firedAt ? `Reached ${formatUtc(a.firedAt)}` : "Waiting"}</small>
                  </span>
                  <button type="button" className="link" aria-label={`Remove alert for ${a.slug.split("-")[0]}`} onClick={() => alerts.remove(a.id)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
