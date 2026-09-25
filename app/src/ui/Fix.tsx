import { CircleAlert, ExternalLink, LifeBuoy, Play, Power, RotateCcw, SearchCheck } from "lucide-react";
import { useState, type ReactElement } from "react";
import { api, ApiError } from "../api";
import { problemFor, type FixAction } from "../fix";
import { useOpenGuide } from "../nav";
import { useStore } from "../state";
import { Button } from "./Button";
import { useToast } from "./Toast";

/** The buttons that fix a problem with one AI (or with the pieces it needs). */
export function FixButtons({ actions, ai, onRetry }: { actions: FixAction[]; ai: string; onRetry?: () => void }) {
  const { estado, refresh, labelOf } = useStore();
  const toast = useToast();
  const openGuide = useOpenGuide();
  const [busy, setBusy] = useState<FixAction | null>(null);
  const info = estado?.ais.find((a) => a.name === ai);
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
      } else if (action === "comprobar") {
        const r = await api.comprobar(ai);
        const text = {
          lista: `${label}: sesión abierta, lista para usar.`,
          sin_sesion: `${label}: no hay sesión. Entra con tu cuenta en la ventanita de webllm.`,
          verificacion: `${label} pide una verificación: resuélvela en la ventanita de webllm.`,
          sin_chrome: "Chrome no está conectado.",
          desconocido: `No pude ver cómo está ${label}. Vuelve a probar.`,
        }[r.session];
        toast(text, r.session === "lista" ? "ok" : "bad");
      } else if (action === "abrir" && info?.url) {
        window.open(info.url, "_blank", "noopener");
      } else if (action === "guia") {
        openGuide();
      } else if (action === "reintentar") {
        onRetry?.();
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
    comprobar: { text: "Comprobar", icon: <SearchCheck size={18} aria-hidden /> },
    abrir: info?.url ? { text: `Abrir ${label} para entrar`, icon: <ExternalLink size={18} aria-hidden /> } : null,
    guia: { text: "Cómo arreglarlo", icon: <LifeBuoy size={18} aria-hidden /> },
    reintentar: onRetry ? { text: "Reintentar", icon: <RotateCcw size={18} aria-hidden /> } : null,
  };
  const shown = actions.filter((a) => buttons[a]);
  if (!shown.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {shown.map((a, i) => (
        <Button
          key={a}
          variant={i === 0 ? "soft" : "secondary"}
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
export function ProblemBox({ code, ai, onRetry }: { code: string; ai: string; onRetry?: () => void }) {
  const { labelOf, estado } = useStore();
  const kind = estado?.ais.find((a) => a.name === ai)?.kind ?? "chat";
  const p = problemFor(code, labelOf(ai), kind);
  return (
    <div className="rounded-xl bg-bad-bg p-4 text-bad-ink" role="alert">
      <div className="flex items-start gap-2.5">
        <CircleAlert size={20} className="mt-0.5 shrink-0" aria-hidden />
        <div className="flex-1">
          <p className="font-semibold">{p.title}</p>
          <p className="mt-0.5 text-[15px] text-ink">{p.text}</p>
        </div>
      </div>
      <div className="mt-3 pl-7">
        <FixButtons actions={p.actions} ai={ai} onRetry={onRetry} />
      </div>
    </div>
  );
}
