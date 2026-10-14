import "@fontsource-variable/red-hat-display";
import "@fontsource-variable/red-hat-text";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";
import { applyTheme, storedTheme } from "./lib/theme";

// Before the first paint, so a light-theme visitor never sees a dark flash.
applyTheme(storedTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
