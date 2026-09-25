import { History, House, Laptop, MessageSquare, Moon, Sun } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { GuideContext, useRoute } from "./nav";
import { Bienvenida, GUIDE_DONE_KEY } from "./screens/Bienvenida";
import { Historial } from "./screens/Historial";
import { Inicio } from "./screens/Inicio";
import { Preguntar } from "./screens/Preguntar";
import { StoreProvider, useStore } from "./state";
import { ToastProvider } from "./ui/Toast";

type Theme = "sistema" | "claro" | "oscuro";
const THEME_KEY = "webllm.tema";
const GUIDE_GRACE_MS = 8000;

function readSetting(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function applyTheme(theme: Theme) {
  const dark = theme === "oscuro" || (theme === "sistema" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function savedTheme(): Theme {
  const t = readSetting(THEME_KEY);
  return t === "claro" || t === "oscuro" ? t : "sistema";
}

function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(savedTheme);
  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // not saved: it just resets next time
    }
    if (theme !== "sistema") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => applyTheme("sistema");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [theme]);
  const options: { value: Theme; label: string; icon: ReactNode }[] = [
    { value: "sistema", label: "Auto", icon: <Laptop size={16} aria-hidden /> },
    { value: "claro", label: "Claro", icon: <Sun size={16} aria-hidden /> },
    { value: "oscuro", label: "Oscuro", icon: <Moon size={16} aria-hidden /> },
  ];
  return (
    <div role="radiogroup" aria-label="Aspecto" className="grid grid-cols-3 gap-1 rounded-xl bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={theme === o.value}
          onClick={() => setTheme(o.value)}
          className={
            "flex min-h-10 cursor-pointer flex-col items-center justify-center rounded-lg text-[15px] font-semibold transition-colors duration-150 " +
            (theme === o.value ? "bg-surface text-ink shadow-card" : "text-muted hover:text-ink")
          }
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  );
}

const NAV = [
  { path: "", label: "Inicio", icon: House },
  { path: "preguntar", label: "Preguntar", icon: MessageSquare },
  { path: "historial", label: "Historial", icon: History },
];

function Logo() {
  return (
    <a href="#/" className="flex items-center gap-2.5 px-2" aria-label="webllm, ir a Inicio">
      <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden>
        <rect width="64" height="64" rx="16" fill="var(--accent)" />
        <circle cx="22" cy="26" r="7" fill="var(--accent-ink)" />
        <circle cx="42" cy="26" r="7" fill="var(--accent-ink)" opacity=".75" />
        <circle cx="32" cy="42" r="7" fill="var(--accent-ink)" opacity=".5" />
      </svg>
      <span className="text-[20px] font-bold tracking-tight">webllm</span>
    </a>
  );
}

function Shell() {
  const route = useRoute();
  const { estado } = useStore();
  const [guide, setGuide] = useState(false);
  const decided = useRef(false);
  const openedAt = useRef(Date.now());
  // The guide only opens by itself when something is missing: Chrome not connected or no chat ready.
  // WEBLLM opens this window while Chrome is still starting, so give the extension a few seconds
  // to connect before deciding (the status is polled every 4 s).
  useEffect(() => {
    if (decided.current || !estado) return;
    const ready = estado.chrome && estado.ais.some((a) => a.kind === "chat" && a.state === "lista");
    if (!ready && Date.now() - openedAt.current < GUIDE_GRACE_MS) return;
    decided.current = true;
    if (!ready && readSetting(GUIDE_DONE_KEY) !== "1") setGuide(true);
  }, [estado]);
  const screen = route[0] ?? "";
  const current = NAV.find((n) => n.path === screen) ? screen : "";
  return (
    <GuideContext.Provider value={() => setGuide(true)}>
      <div className="flex h-full flex-col md:flex-row">
        <nav aria-label="Pantallas" className="flex shrink-0 flex-col gap-4 border-b border-line bg-surface px-3 py-3 md:w-60 md:border-b-0 md:border-r md:px-4 md:py-6">
          <div className="flex items-center justify-between md:block">
            <Logo />
          </div>
          <ul className="flex gap-1 md:mt-4 md:flex-col">
            {NAV.map(({ path, label, icon: Icon }) => (
              <li key={label} className="flex-1 md:flex-none">
                <a
                  href={`#/${path}`}
                  aria-current={current === path ? "page" : undefined}
                  className={
                    "flex min-h-12 items-center justify-center gap-3 rounded-xl px-3 text-[16px] font-semibold transition-colors duration-150 md:justify-start " +
                    (current === path ? "bg-accent-soft text-accent-soft-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink")
                  }
                >
                  <Icon size={20} aria-hidden />
                  {label}
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-auto hidden flex-col gap-3 md:flex">
            <ThemeSwitch />
            <p className="px-1 text-[15px] leading-snug text-muted">Todo se guarda en tu PC. Nada pasa por la nube salvo los propios chats.</p>
          </div>
        </nav>
        <main className="min-w-0 flex-1 overflow-y-auto">
          {screen === "preguntar" && <Preguntar />}
          {screen === "historial" && <Historial id={route[1]} />}
          {screen !== "preguntar" && screen !== "historial" && <Inicio />}
          <div className="px-5 pb-6 md:hidden">
            <ThemeSwitch />
          </div>
        </main>
      </div>
      <Bienvenida open={guide} onClose={() => setGuide(false)} />
    </GuideContext.Provider>
  );
}

export function App() {
  return (
    <ToastProvider>
      <StoreProvider>
        <Shell />
      </StoreProvider>
    </ToastProvider>
  );
}
