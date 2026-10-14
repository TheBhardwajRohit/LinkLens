// Dark is the default look; a visitor can switch to light, and the choice is remembered on this
// device only. Storage can be refused (private windows), so every read and write is guarded.

export type Theme = "dark" | "light";
const KEY = "linklens-theme";

export function storedTheme(): Theme {
  try {
    return window.localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    // Not remembered, but still applied for this visit.
  }
}
