import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "../ui.css";
import { Popup } from "./Popup";

document.body.style.margin = "0";
document.body.style.background = "#07080c";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Popup />
  </StrictMode>,
);
