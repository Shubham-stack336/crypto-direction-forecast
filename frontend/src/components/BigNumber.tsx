import { formatPrice } from "../format";

/** A large price. The digits that carry the least information are dimmed. */
export function BigNumber({ value }: { value: number }) {
  const text = formatPrice(value);
  const zeros = /^0\.0*/.exec(text)?.[0] ?? "";
  const dot = text.indexOf(".");
  const parts = zeros
    ? [zeros, text.slice(zeros.length), ""]
    : dot === -1 ? ["", text, ""] : ["", text.slice(0, dot), text.slice(dot)];
  return (
    <p className="big-number" aria-label={text}>
      <span className="dim">{parts[0]}</span>{parts[1]}<span className="dim">{parts[2]}</span>
    </p>
  );
}
