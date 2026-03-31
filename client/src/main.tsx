import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserBlocked } from "./components/BrowserBlocked";
import App from "./App.tsx";
import "./styles/globals.css";

function isDesktopShell(): boolean {
  if (import.meta.env.VITE_ALLOW_BROWSER === "true") {
    return true;
  }
  return typeof window !== "undefined" && !!window.electronAPI;
}

const root = document.getElementById("root")!;

createRoot(root).render(
  <StrictMode>
    {isDesktopShell() ? <App /> : <BrowserBlocked />}
  </StrictMode>,
);
