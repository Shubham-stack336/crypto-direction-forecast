import { useTheme, type Theme } from "../theme";
import { Icon } from "./Icon";

const NEXT: Record<Theme, Theme> = { system: "dark", dark: "light", light: "system" };
const NAME: Record<Theme, string> = { system: "Match device", dark: "Night", light: "Day" };
const ICON = { system: "device", dark: "moon", light: "sun" } as const;

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <button
      type="button"
      className="round"
      title={`Theme: ${NAME[theme]}`}
      aria-label={`Theme: ${NAME[theme]}. Switch to ${NAME[NEXT[theme]]}`}
      onClick={() => setTheme(NEXT[theme])}
    >
      <Icon name={ICON[theme]} />
    </button>
  );
}
