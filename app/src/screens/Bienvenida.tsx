import { Check, CircleCheck, ClipboardCopy, ExternalLink, Loader2, SearchCheck, Send } from "lucide-react";
import { useState, type ReactNode } from "react";
import { api } from "../api";
import { go } from "../nav";
import { useStore } from "../state";
import { AiAvatar } from "../ui/Ai";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Badge, DoneBadge, WorkingBadge } from "../ui/Status";
import { useToast } from "../ui/Toast";
import stepToggle from "../assets/guia-modo-desarrollador.png";
import stepLoad from "../assets/guia-cargar-descomprimida.png";

export const GUIDE_DONE_KEY = "webllm.guia-hecha";

type Session = "lista" | "sin_sesion" | "verificacion" | "sin_chrome" | "desconocido" | "mirando";

function CopyLine({ text }: { text: string }) {
  const toast = useToast();
  return (
    <span className="mt-1.5 flex flex-wrap items-center gap-2">
      <code className="break-all rounded-lg bg-code px-2.5 py-1.5 font-mono text-[15px]">{text}</code>
      <Button
        variant="secondary"
        icon={<ClipboardCopy size={17} aria-hidden />}
        onClick={() => navigator.clipboard.writeText(text).then(() => toast("Copiado."), () => toast("No se pudo copiar.", "bad"))}
      >
        Copiar
      </Button>
    </span>
  );
}

function Stepper({ step, done }: { step: number; done: boolean[] }) {
  const names = ["Instalar la extensión", "Entrar en tus chats", "Primera pregunta"];
  return (
    <ol className="mb-6 grid grid-cols-3 gap-2">
      {names.map((n, i) => (
        <li key={n} className="flex flex-col items-center gap-1.5 text-center">
          <span
            className={
              "flex h-9 w-9 items-center justify-center rounded-full text-[16px] font-bold " +
              (done[i] ? "bg-ok-bg text-ok-ink" : i === step ? "bg-accent text-accent-ink" : "bg-surface-2 text-muted")
            }
          >
            {done[i] ? <Check size={18} strokeWidth={3} aria-label="hecho" /> : i + 1}
          </span>
          <span className={`text-[15px] ${i === step ? "font-semibold text-ink" : "text-muted"}`}>{n}</span>
        </li>
      ))}
    </ol>
  );
}

function Shot({ src, alt }: { src: string; alt: string }) {
  return <img src={src} alt={alt} className="mt-2 w-full max-w-md rounded-xl border border-line" />;
}

function Done({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl bg-ok-bg px-4 py-3 font-semibold text-ok-ink" role="status">
      <CircleCheck size={20} aria-hidden />
      {children}
    </div>
  );
}

export function Bienvenida({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { estado, ask, turns } = useStore();
  const [step, setStep] = useState(0);
  const [sessions, setSessions] = useState<Record<string, Session>>({});
  const [question, setQuestion] = useState("¿Qué tiempo suele hacer en Madrid en octubre? Respóndeme en 3 frases.");
  const [turnId, setTurnId] = useState<string | null>(null);

  const chats = (estado?.ais ?? []).filter((a) => a.kind === "chat");
  const turn = turns.find((t) => t.id === turnId);
  const done = [
    !!estado?.chrome,
    Object.values(sessions).includes("lista"),
    !!turn?.answers.some((a) => a.phase === "done" && a.ok),
  ];

  const finish = () => {
    try {
      localStorage.setItem(GUIDE_DONE_KEY, "1");
    } catch {
      // private window: the guide will show again next time, which is harmless
    }
    onClose();
  };

  const check = async (name: string) => {
    setSessions((s) => ({ ...s, [name]: "mirando" }));
    try {
      const r = await api.comprobar(name);
      setSessions((s) => ({ ...s, [name]: r.session }));
    } catch {
      setSessions((s) => ({ ...s, [name]: "desconocido" }));
    }
  };

  const sessionBadge = (s: Session | undefined) => {
    if (!s) return null;
    if (s === "mirando") return <WorkingBadge>Mirando…</WorkingBadge>;
    if (s === "lista") return <DoneBadge ok>Sesión abierta</DoneBadge>;
    const words = { sin_sesion: "Sin sesión", verificacion: "Pide verificación", sin_chrome: "Falta Chrome", desconocido: "No se pudo ver" };
    return <DoneBadge ok={false}>{words[s]}</DoneBadge>;
  };

  return (
    <Modal open={open} onOpenChange={(o) => !o && finish()} title="Bienvenido a webllm" description="Tres pasos y listo. Cada paso se pone en verde él solo cuando está hecho." wide>
      <Stepper step={step} done={done} />

      {step === 0 && (
        <div className="flex flex-col gap-4">
          {done[0] ? (
            <Done>Chrome está conectado con la extensión. Pasa al siguiente paso.</Done>
          ) : (
            <p className="text-ink-2">
              La extensión es lo que deja a webllm escribir en tus chats de IA dentro de tu Chrome. Se instala una sola vez.
            </p>
          )}
          <ol className="flex list-decimal flex-col gap-4 pl-6">
            <li>
              Abre una pestaña nueva en Chrome, pega esto en la barra de direcciones y pulsa Enter:
              <CopyLine text="chrome://extensions" />
            </li>
            <li>
              Arriba a la <b>derecha</b>, enciende <b>Modo Desarrollador</b>.
              <Shot src={stepToggle} alt="El interruptor «Modo Desarrollador», arriba a la derecha de la página de extensiones" />
            </li>
            <li>
              Arriba a la <b>izquierda</b>, pulsa <b>Cargar descomprimida</b> y elige esta carpeta:
              <Shot src={stepLoad} alt="El botón «Cargar descomprimida», arriba a la izquierda de la página de extensiones" />
              <CopyLine text={estado?.extension_path ?? "…"} />
            </li>
          </ol>
          {!done[0] && (
            <p className="flex items-center gap-2 text-[15px] text-muted">
              <Loader2 size={16} className="animate-spin" aria-hidden /> Esperando a que Chrome se conecte…
            </p>
          )}
        </div>
      )}

      {step === 1 && (
        <div className="flex flex-col gap-4">
          <p className="text-ink-2">
            Entra con tu cuenta en cada chat que quieras usar y pulsa <b>Comprobar</b>. No se envía ningún mensaje. Con uno basta para empezar.
          </p>
          {!estado?.chrome && <p className="font-semibold text-bad-ink">Primero termina el paso 1: Chrome todavía no está conectado.</p>}
          <div className="flex flex-col gap-2">
            {chats.map((a) => (
              <div key={a.name} data-ai={a.name} className="flex flex-wrap items-center gap-3 rounded-xl border border-line px-4 py-3">
                <AiAvatar name={a.name} label={a.label} size={34} />
                <span className="flex-1 text-[17px] font-semibold">{a.label}</span>
                {sessionBadge(sessions[a.name])}
                {a.url && (
                  <Button variant="secondary" icon={<ExternalLink size={17} aria-hidden />} onClick={() => window.open(a.url!, "_blank", "noopener")}>
                    Abrir
                  </Button>
                )}
                <Button variant="soft" icon={<SearchCheck size={17} aria-hidden />} onClick={() => check(a.name)} disabled={sessions[a.name] === "mirando"}>
                  Comprobar
                </Button>
              </div>
            ))}
          </div>
          {done[1] && <Done>¡Bien! Ya tienes al menos un chat listo.</Done>}
        </div>
      )}

      {step === 2 && (
        <div className="flex flex-col gap-4">
          <p className="text-ink-2">Haz tu primera pregunta a todas las IAs que están listas. Puedes cambiar el texto.</p>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            aria-label="Tu primera pregunta"
            className="w-full resize-y rounded-xl border border-line-strong bg-surface p-3 text-[16px] text-ink focus:border-accent focus:outline-none"
          />
          {!turn && (
            <div>
              <Button
                variant="primary"
                size="lg"
                icon={<Send size={20} aria-hidden />}
                disabled={!question.trim() || !(estado?.ais ?? []).some((a) => a.state === "lista")}
                onClick={() =>
                  ask({ prompt: question.trim(), to: (estado?.ais ?? []).filter((a) => a.state === "lista").map((a) => a.name), onStart: setTurnId })
                }
              >
                Preguntar a todas las que están listas
              </Button>
            </div>
          )}
          {turn && (
            <div className="flex flex-col gap-2">
              {turn.answers.map((a) => (
                <div key={a.target} className="flex items-center gap-3 rounded-xl border border-line px-4 py-2.5">
                  <AiAvatar name={a.target} label={a.label} size={30} />
                  <span className="flex-1 font-semibold">{a.label}</span>
                  {a.phase === "waiting" && <Badge tone="neutral" icon={<Loader2 size={16} className="animate-spin" aria-hidden />}>En cola</Badge>}
                  {a.phase === "asking" && <WorkingBadge>Esperando…</WorkingBadge>}
                  {a.phase === "done" && <DoneBadge ok={a.ok}>{a.ok ? "Respondió" : "No respondió"}</DoneBadge>}
                </div>
              ))}
            </div>
          )}
          {done[2] && <Done>¡Hecho! Ya sabes usar webllm.</Done>}
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
        <Button variant="ghost" onClick={finish}>
          Saltar la guía
        </Button>
        <div className="flex gap-2">
          {step > 0 && (
            <Button variant="secondary" onClick={() => setStep(step - 1)}>
              Atrás
            </Button>
          )}
          {step < 2 ? (
            <Button variant={done[step] ? "primary" : "secondary"} onClick={() => setStep(step + 1)}>
              {done[step] ? "Siguiente" : "Seguir sin esto"}
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => {
                finish();
                go("preguntar");
              }}
            >
              {done[2] ? "Ver las respuestas" : "Terminar"}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
