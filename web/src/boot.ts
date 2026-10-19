// What both pages need before they draw: the fonts, the styles, and the saved theme.
import "@fontsource-variable/red-hat-display";
import "@fontsource-variable/red-hat-text";

import "./index.css";
import { applyTheme, storedTheme } from "./lib/theme";

// Before the first paint, so a light-theme visitor never sees a dark flash.
applyTheme(storedTheme());
