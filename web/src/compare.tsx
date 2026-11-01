import "./boot";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import ComparePage from "./compare/ComparePage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ComparePage />
  </StrictMode>,
);
