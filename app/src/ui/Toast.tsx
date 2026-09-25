import { CircleAlert, CircleCheck, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

interface Toast {
  id: number;
  text: string;
  tone: "ok" | "bad";
}

const Ctx = createContext<(text: string, tone?: "ok" | "bad") => void>(() => {});

export const useToast = () => useContext(Ctx);

/** Small notices top-right that disappear by themselves. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const close = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const show = useCallback(
    (text: string, tone: "ok" | "bad" = "ok") => {
      const id = next.current++;
      setToasts((t) => [...t.slice(-3), { id, text, tone }]);
      window.setTimeout(() => close(id), tone === "ok" ? 3500 : 7000);
    },
    [close],
  );
  const value = useMemo(() => show, [show]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div aria-live="polite" role="status" className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(420px,calc(100vw-32px))] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="animate-pop pointer-events-auto flex items-start gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-[15px] shadow-pop"
          >
            {t.tone === "ok" ? (
              <CircleCheck size={20} className="mt-0.5 shrink-0 text-ok-ink" aria-hidden />
            ) : (
              <CircleAlert size={20} className="mt-0.5 shrink-0 text-bad-ink" aria-hidden />
            )}
            <span className="flex-1">{t.text}</span>
            <button type="button" onClick={() => close(t.id)} className="cursor-pointer rounded-md p-0.5 text-muted hover:text-ink" aria-label="Cerrar aviso">
              <X size={18} />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
