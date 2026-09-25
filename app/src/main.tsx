import "@fontsource-variable/inter";
import "./styles.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App, applyTheme, savedTheme } from "./App";

applyTheme(savedTheme());
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
