import "./boot";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import Home from "./home/Home";
import { SCANNER } from "./lib/pages";

// Result links used to point at the homepage (/?scan=<id>). Send them on to the scanner page.
const shared = new URLSearchParams(window.location.search).get("scan");
if (shared) {
  window.location.replace(`${SCANNER}?scan=${encodeURIComponent(shared)}`);
} else {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <Home />
    </StrictMode>,
  );
}
