import { createContext, useContext, useEffect, useState } from "react";

/** Screens live in the URL hash (#/preguntar, #/historial/<id>) so reloading keeps your place. */
export function useRoute(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [parts, setParts] = useState(read);
  useEffect(() => {
    const on = () => setParts(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return parts;
}

export const go = (path: string) => {
  window.location.hash = `#/${path}`;
};

/** Opens the first-time guide from anywhere (for example from a "Chrome no está conectado" box). */
export const GuideContext = createContext<() => void>(() => {});
export const useOpenGuide = () => useContext(GuideContext);

/** Opens "Añadir otra IA" from anywhere (Inicio, the AI picker). */
export const AddAiContext = createContext<() => void>(() => {});
export const useOpenAddAi = () => useContext(AddAiContext);
