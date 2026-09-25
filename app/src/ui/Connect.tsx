import { Loader2, Plug } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Session } from "../api";
import { useStore } from "../state";
import { Button } from "./Button";
import { DoneBadge } from "./Status";
import { useToast } from "./Toast";

const EVERY_MS = 3000;
const GIVE_UP_MS = 3 * 60 * 1000;

type Phase = "idle" | "opening" | "waiting" | "done" | "gave_up" | "no_chrome";

/**
 * "Conectar": opens the chat in the small webllm window (bringing it forward when there is no
 * session), then looks again every 3 s for up to 3 minutes until the session is there. No second
 * click needed. Nothing is ever sent to the chat.
 */
export function ConnectButton({ ai, onConnected }: { ai: string; onConnected?: () => void }) {
  const { labelOf, refresh } = useStore();
  const toast = useToast();
  const [phase, setPhase] = useState<Phase>("idle");
  const [hint, setHint] = useState("");
  const [seconds, setSeconds] = useState(0);
  const run = useRef(0); // bumps on cancel/unmount so an old polling loop stops
  const label = labelOf(ai);

  useEffect(() => () => void run.current++, []);

  const connected = async () => {
    setPhase("done");
    toast(`${label} conectada. Ya puedes preguntarle.`);
    onConnected?.();
    await refresh();
  };

  const explain = (session: Session, shown: boolean) => {
    if (session === "verificacion") return `${label} pide una verificación: resuélvela en la ventana de webllm. Te espero aquí.`;
    const where = shown ? "en la ventana de webllm que acabo de traer al frente" : "en la ventanita de webllm (abajo a la derecha de la pantalla)";
    return `Entra en ${label} con tu cuenta ${where}. Te espero aquí; no hace falta que vuelvas a pulsar nada.`;
  };

  const start = async () => {
    const mine = ++run.current;
    setPhase("opening");
    try {
      const first = await api.conectar(ai);
      if (mine !== run.current) return;
      if (first.session === "lista") return connected();
      if (first.session === "sin_chrome") {
        setPhase("no_chrome");
        return;
      }
      setHint(explain(first.session, first.shown));
      setPhase("waiting");
      const t0 = Date.now();
      while (mine === run.current && Date.now() - t0 < GIVE_UP_MS) {
        await new Promise((r) => window.setTimeout(r, EVERY_MS));
        if (mine !== run.current) return;
        setSeconds(Math.round((Date.now() - t0) / 1000));
        const r = await api.comprobar(ai).catch(() => ({ session: "desconocido" as Session }));
        if (mine !== run.current) return;
        if (r.session === "lista") return connected();
        if (r.session === "verificacion") setHint(explain("verificacion", true));
      }
      if (mine === run.current) setPhase("gave_up");
    } catch (err) {
      if (mine !== run.current) return;
      toast(err instanceof ApiError ? err.message : "No pude abrir el chat.", "bad");
      setPhase("idle");
    }
  };

  const stop = () => {
    run.current++;
    setPhase("idle");
  };

  if (phase === "done") return <DoneBadge ok>Conectada</DoneBadge>;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {phase === "waiting" ? (
        <>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-[15px] font-semibold text-accent-soft-ink">
            <Loader2 size={16} className="animate-spin" aria-hidden /> Esperando a que entres… {seconds} s
          </span>
          <Button size="sm" variant="ghost" onClick={stop}>
            Dejar de esperar
          </Button>
          <p className="basis-full text-[15px] text-ink-2" role="status">
            {hint}
          </p>
        </>
      ) : (
        <>
          <Button variant="soft" icon={<Plug size={18} aria-hidden />} onClick={start} disabled={phase === "opening"}>
            {phase === "opening" ? "Abriendo…" : phase === "gave_up" ? "Conectar otra vez" : "Conectar"}
          </Button>
          {phase === "gave_up" && (
            <p className="basis-full text-[15px] text-ink-2">Pasaron 3 minutos y no vi la sesión abierta. Cuando hayas entrado, pulsa otra vez.</p>
          )}
          {phase === "no_chrome" && (
            <p className="basis-full text-[15px] text-bad-ink">Chrome no está conectado: abre Chrome con la extensión webllm y vuelve a pulsar.</p>
          )}
        </>
      )}
    </div>
  );
}
