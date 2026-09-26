import { ArrowRightLeft, CircleAlert, LifeBuoy, Play, Power, RotateCcw } from "lucide-react";
import { useState, type ReactElement } from "react";
import { api, ApiError } from "../api";
import { problemFor, type FixAction } from "../fix";
import { useOpenGuide } from "../nav";
import { useStore } from "../state";
import { Button } from "./Button";
import { ConnectButton } from "./Connect";
import { useToast } from "./Toast";

/** The buttons that fix a problem with one AI (or with the pieces it needs). */
export function FixButtons({ actions, ai, onRetry, onAskOther }: {
  actions: FixAction[];
  ai: string;
  onRetry?: () => void;
  /** Ask the same question to another AI (only when Iván presses it: nothing changes on its own). */
  onAskOther?: (other: string) => void;
}) {
  const { refresh, labelOf, estado } = useStore();
  const info = estado?.ais.find((a) => a.name === ai);
  // The other AI offered: one that is ready, APIs first (fast, no account), then this PC, then chats.
  const other = ["api", "local", "chat"]
    .map((kind) => estado?.ais.find((a) => a.kind === kind && a.name !== ai && a.state === "lista"))
    .find(Boolean);
  const serverName = info?.server_name ?? "el programa";
  const toast = useToast();
  const openGuide = useOpenGuide();
  const [busy, setBusy] = useState<FixAction | null>(null);
  const label = labelOf(ai);

  const run = async (action: FixAction) => {
    setBusy(action);
    try {
      if (action === "reanudar") {
        await api.reanudar(ai);
        toast(`${label} vuelve a estar activa.`);
      } else if (action === "encender") {
        const r = await api.encenderOmniroute();
        toast(r.already ? "Ya estaba encendido." : "Encendiendo las IAs por API… tarda unos segundos.");
      } else if (action === "encender_local" && info?.server) {
        const r = await api.encenderLocal(info.server);
        toast(r.already ? `${serverName} ya estaba encendido.` : `Encendiendo ${serverName}… tarda unos segundos.`);
      } else if (action === "guia") {
        openGuide();
      } else if (action === "reintentar") {
        onRetry?.();
      } else if (action === "otra" && other) {
        onAskOther?.(other.name);
      }
      await refresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo hacer.", "bad");
    } finally {
      setBusy(null);
    }
  };

  const buttons: Record<FixAction, { text: string; icon: ReactElement } | null> = {
    reanudar: { text: "Reanudar", icon: <Play size={18} aria-hidden /> },
    encender: { text: "Encender", icon: <Power size={18} aria-hidden /> },
    conectar: null, // its own component: it keeps looking until the session is there
    encender_local: info?.server ? { text: `Encender ${serverName}`, icon: <Power size={18} aria-hidden /> } : null,
    guia: { text: "Cómo arreglarlo", icon: <LifeBuoy size={18} aria-hidden /> },
    reintentar: onRetry ? { text: "Reintentar", icon: <RotateCcw size={18} aria-hidden /> } : null,
    otra: onAskOther && other ? { text: `Preguntar a ${other.label}`, icon: <ArrowRightLeft size={18} aria-hidden /> } : null,
  };
  const shown = actions.filter((a) => buttons[a]);
  const connect = actions.includes("conectar");
  if (!shown.length && !connect) return null;
  return (
    <div className="flex flex-wrap items-start gap-2">
      {connect && <ConnectButton ai={ai} />}
      {shown.map((a, i) => (
        <Button
          key={a}
          variant={i === 0 && !connect ? "soft" : "secondary"}
          icon={buttons[a]!.icon}
          onClick={() => run(a)}
          disabled={busy !== null}
        >
          {busy === a ? "Un momento…" : buttons[a]!.text}
        </Button>
      ))}
    </div>
  );
}

/** What happened + what to do + the button that fixes it. */
export function ProblemBox({ code, ai, said, onRetry, onAskOther }: {
  code: string;
  ai: string;
  /** What the AI's service answered, word for word (shown when webllm has no better explanation). */
  said?: string;
  onRetry?: () => void;
  onAskOther?: (other: string) => void;
}) {
  const { labelOf, estado } = useStore();
  const info = estado?.ais.find((a) => a.name === ai);
  const p = problemFor(code, labelOf(ai), info?.kind ?? "chat", info?.server_name ?? "");
  return (
    <div className="rounded-xl bg-bad-bg p-4 text-bad-ink" role="alert">
      <div className="flex items-start gap-2.5">
        <CircleAlert size={20} className="mt-0.5 shrink-0" aria-hidden />
        <div className="flex-1">
          <p className="font-semibold">{p.title}</p>
          <p className="mt-0.5 text-[15px] text-ink">{p.text}</p>
          {p.said && said?.trim() && (
            <p className="mt-1.5 break-words text-[15px] text-ink">
              Lo que respondió: «{said.trim().length > 200 ? said.trim().slice(0, 200) + "…" : said.trim()}»
            </p>
          )}
        </div>
      </div>
      <div className="mt-3 pl-7">
        <FixButtons actions={p.actions} ai={ai} onRetry={onRetry} onAskOther={onAskOther} />
      </div>
    </div>
  );
}
