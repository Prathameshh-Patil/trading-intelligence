import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import SidePanel from "./SidePanel.tsx";
import { installWebviewLogBridge } from "./lib/webviewLog";

// Installed before render so anything thrown during the first mount is caught.
installWebviewLogBridge();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SidePanel />
  </StrictMode>,
);
