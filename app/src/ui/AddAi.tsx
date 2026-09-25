import { CircleAlert, CircleCheck, ClipboardCopy, Loader2, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type AddState, type AddStep } from "../api";
import { useStore } from "../state";
import { Button } from "./Button";
import { Modal } from "./Modal";
import { useToast } from "./Toast";

const EVERY_MS = 1000;
// Permission click + opening the site + a 2-minute answer: never wait forever.
const GIVE_UP_MS = 5 * 60 * 1000;

// The order the steps happen in (the extension reports each one as it goes).
const ORDER = ["permission", "open", "input", "send", "read"];
const WAITING_TEXT: Record<string, string> = {
  permission: "Tu permiso en Chrome",
  open: "Abrir la web",
  input: "Encontrar la caja de texto",
  send: "Enviar una prueba («pong»)",
  read: "Leer la respuesta",
};

function StepRow({ step }: { step: AddStep | { step: string; ok: undefined; text: string } }) {
  const icon =
    step.ok === true ? (
      <CircleCheck size={20} className="text-ok-ink" aria-label="hecho" />
    ) : step.ok === false ? (
      <CircleAlert size={20} className="text-bad-ink" aria-label="falló" />
    ) : step.ok === null ? (
      <Loader2 size={20} className="animate-spin text-accent" aria-label="en marcha" />
    ) : (
      <span className="block h-5 w-5 rounded-full border-2 border-line-strong" aria-label="pendiente" />
    );
  return (
    <li className={`flex items-center gap-3 py-1.5 ${step.ok === undefined ? "text-muted" : "text-ink"}`}>
      <span className="flex h-5 w-5 shrink-0 items-center justify-center">{icon}</span>
      <span className="text-[16px]">{step.text}</span>
    </li>
  );
}

/** The steps so far, plus the ones still to come in grey (so Iván sees how long the test is). */
function Steps({ st }: { st: AddState }) {
  const seen = new Map(st.steps.map((s) => [s.step, s]));
  const failedAt = st.status === "failed" ? ORDER.find((k) => !seen.get(k)?.ok) : undefined;
  const rows = ORDER.map((k) => {
    const s = seen.get(k);
    if (s && !(st.status === "failed" && s.ok === null)) return s;
    if (k === failedAt) return { step: k, ok: false as const, text: WAITING_TEXT[k] };
    return { step: k, ok: undefined, text: WAITING_TEXT[k] };
  });
  return (
    <ol className="rounded-xl border border-line px-4 py-2" aria-label="Pasos de la prueba">
      {rows.map((s) => (
        <StepRow key={s.step} step={s} />
      ))}
    </ol>
  );
}

/**
 * "+ Añadir otra IA": paste the address of a chat website, Chrome asks permission for that one
 * site, and the extension really uses it once ("pong") before it is saved. Every step shows.
 */
export function AddAiDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { estado, refresh } = useStore();
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [st, setSt] = useState<AddState | null>(null);
  const run = useRef(0);
  const isOpen = useRef(open);

  useEffect(() => () => void run.current++, []);
  useEffect(() => {
    isOpen.current = open;
  }, [open]);

  const reset = () => {
    run.current++;
    setSt(null);
    setError("");
    setBusy(false);
  };

  const start = async () => {
    const mine = ++run.current;
    setError("");
    setBusy(true);
    setSt(null);
    try {
      let s = await api.anadir(url);
      if (mine !== run.current) return;
      setSt(s);
      const t0 = Date.now();
      while (s.status === "running" && mine === run.current && Date.now() - t0 < GIVE_UP_MS) {
        await new Promise((r) => window.setTimeout(r, EVERY_MS));
        if (mine !== run.current) return;
        s = await api.anadirEstado(s.add_id).catch(() => s);
        if (mine !== run.current) return;
        setSt(s);
      }
      if (s.status === "running") {
        s = { ...s, status: "failed", error: "gave_up", message: "Pasaron 5 minutos sin terminar la prueba. Mira la pestaña «Añadir a webllm» en Chrome." };
        setSt(s);
      }
      if (s.status === "ok") await refresh();
      // Closed while the test ran: the result comes as a notice instead.
      if (!isOpen.current) toast(s.status === "ok" ? `${s.name} añadida: ya puedes preguntarle.` : s.message, s.status === "ok" ? "ok" : "bad");
    } catch (err) {
      if (mine !== run.current) return;
      setError(err instanceof ApiError ? err.message : "No se pudo empezar la prueba.");
    } finally {
      if (mine === run.current) setBusy(false);
    }
  };

  const copyDiagnosis = (s: AddState) => {
    const text = [`webllm: añadir ${s.name}`, `Dirección: ${s.url}`, `Resultado: ${s.error}`, ...s.steps.map((x) => `- ${x.text}: ${x.ok}`), "", s.detail].join("\n");
    navigator.clipboard.writeText(text).then(
      () => toast("Diagnóstico copiado. Pégaselo a quien te ayude con webllm."),
      () => toast("No se pudo copiar.", "bad"),
    );
  };

  const running = busy && (!st || st.status === "running");

  const close = () => {
    onOpenChange(false);
    // A running test keeps going (reopen to see it); otherwise start clean next time,
    // but keep the address if the test failed (to fix a typo).
    if (running) return;
    if (st?.status === "ok") setUrl("");
    reset();
  };
  const waitingPermission = st?.status === "running" && st.steps.length === 1 && st.steps[0].step === "permission";

  return (
    <Modal
      open={open}
      onOpenChange={(o) => (o ? onOpenChange(true) : close())}
      title="Añadir otra IA"
      description="Pega la dirección de una web de chat de IA en la que tengas cuenta. webllm la prueba de verdad antes de guardarla."
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim() && !running) start();
        }}
      >
        <label className="flex flex-col gap-1.5">
          <span className="font-semibold">Dirección de la web</span>
          <input
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={url}
            readOnly={running}
            onChange={(e) => {
              setUrl(e.target.value);
              setError("");
            }}
            placeholder="https://chat.mistral.ai"
            aria-invalid={!!error}
            aria-describedby={st ? undefined : "add-ai-help"}
            className="min-h-12 w-full rounded-xl border border-line-strong bg-surface px-3.5 text-[16px] text-ink placeholder:text-muted focus:border-accent focus:outline-none read-only:bg-surface-2 read-only:text-ink-2"
          />
          {!st && (
            <span id="add-ai-help" className="text-[15px] text-muted">
              Cópiala de la barra de direcciones de Chrome cuando tengas abierta esa IA.
            </span>
          )}
        </label>
        {error && (
          <p className="flex items-start gap-2 rounded-xl bg-bad-bg px-4 py-3 text-[15px] text-bad-ink" role="alert">
            <CircleAlert size={20} className="mt-0.5 shrink-0" aria-hidden />
            <span>
              {error}
              {!estado?.chrome && " Abre Chrome con la extensión webllm."}
            </span>
          </p>
        )}
        {!st && (
          <div>
            <Button type="submit" variant="primary" icon={<Plus size={19} aria-hidden />} disabled={!url.trim() || running}>
              {running ? "Un momento…" : "Probar y añadir"}
            </Button>
          </div>
        )}
      </form>

      {st && (
        <div className="mt-5 flex flex-col gap-4">
          {waitingPermission && (
            <p className="rounded-xl bg-accent-soft px-4 py-3 text-[15px] text-accent-soft-ink" role="status">
              Chrome ha abierto una pestaña <b>«Añadir {st.name} a webllm»</b>. Pulsa allí <b>Permitir y probar</b> y luego <b>Permitir</b> en el aviso de
              Chrome. El resto lo hace webllm solo.
            </p>
          )}
          <Steps st={st} />
          {st.status === "ok" && (
            <p className="flex items-start gap-2.5 rounded-xl bg-ok-bg px-4 py-3 font-semibold text-ok-ink" role="status">
              <CircleCheck size={20} className="mt-0.5 shrink-0" aria-hidden />
              {st.message}
            </p>
          )}
          {st.status === "failed" && (
            <div className="rounded-xl bg-bad-bg p-4 text-bad-ink" role="alert">
              <p className="flex items-start gap-2.5 font-semibold">
                <CircleAlert size={20} className="mt-0.5 shrink-0" aria-hidden />
                {st.message}
              </p>
              {["no_input", "insert_failed", "empty_answer", "unexpected_answer", "not_sent"].includes(st.error) && (
                <p className="mt-1.5 pl-7 text-[15px] text-ink">
                  Algunas webs están hechas de una forma que webllm todavía no sabe manejar. No se ha guardado nada.
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2 pl-7">
                {st.error !== "cancelled" && (
                  <Button variant="secondary" icon={<RotateCcw size={18} aria-hidden />} onClick={start}>
                    Probar otra vez
                  </Button>
                )}
                {st.detail && (
                  <Button variant="ghost" icon={<ClipboardCopy size={18} aria-hidden />} onClick={() => copyDiagnosis(st)}>
                    Copiar diagnóstico
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="sticky bottom-[-24px] -mx-6 -mb-6 mt-6 flex flex-wrap items-center justify-between gap-2 rounded-b-2xl border-t border-line bg-surface px-6 py-4">
        <p className="text-[15px] text-muted">Claude y ChatGPT no se pueden añadir.</p>
        <div className="flex gap-2">
          {st && st.status !== "running" && st.status !== "ok" && (
            <Button variant="ghost" onClick={reset}>
              Otra dirección
            </Button>
          )}
          <Button variant={st?.status === "ok" ? "primary" : "secondary"} onClick={close}>
            {st?.status === "ok" ? "Hecho" : running ? "Cerrar (la prueba sigue)" : "Cerrar"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** "Quitar" on an AI added from the app (asks first; the built-in ones cannot be removed). */
export function RemoveAiButton({ name, label }: { name: string; label: string }) {
  const { refresh } = useStore();
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!asking)
    return (
      <Button variant="ghost" size="sm" icon={<Trash2 size={17} aria-hidden />} onClick={() => setAsking(true)}>
        Quitar
      </Button>
    );
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={`Quitar ${label}`}>
      <span className="text-[15px] font-semibold">¿Quitar {label} de webllm?</span>
      <Button
        variant="secondary"
        size="sm"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api.quitar(name);
            toast(`${label} quitada. Tu cuenta en esa web sigue igual.`);
            await refresh();
          } catch (err) {
            toast(err instanceof ApiError ? err.message : "No se pudo quitar.", "bad");
            setBusy(false);
            setAsking(false);
          }
        }}
      >
        {busy ? "Quitando…" : "Sí, quitar"}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setAsking(false)} disabled={busy}>
        No
      </Button>
    </div>
  );
}
