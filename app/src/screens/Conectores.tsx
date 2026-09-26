import { CircleAlert, CircleCheck, CircleSlash, ClipboardCopy, EyeOff, Gauge, Globe, Loader2, MousePointerClick, Plug, Plus, RotateCcw, ShieldAlert, Square, UserRound } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type Batch, type BatchResult, type CatalogAi, type Catalogo } from "../api";
import { useOpenAddAi } from "../nav";
import { useStore } from "../state";
import { StepRow } from "../ui/AddAi";
import { AiAvatar } from "../ui/Ai";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Empty } from "../ui/Empty";
import { FichaDialog } from "../ui/Ficha";
import { Modal } from "../ui/Modal";
import { Page, SectionTitle } from "../ui/Page";
import { RepararCard } from "../ui/Reparar";
import { Badge } from "../ui/Status";
import { useToast } from "../ui/Toast";
import { AiCard } from "./Inicio";

const EVERY_MS = 1000;
const ICON = { size: 16, strokeWidth: 2.25, "aria-hidden": true } as const;

/** What Iván reads about one chat before connecting it: what to know (nothing when there is nothing). */
function Facts({ ai, defaultCap }: { ai: CatalogAi; defaultCap: number }) {
  const lowCap = ai.daily_cap < defaultCap;
  if (ai.private && ai.group !== "2" && ai.account !== "no" && ai.account !== "si" && !lowCap) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {!ai.private && (
        <Badge tone="bad" icon={<EyeOff {...ICON} />}>
          No privada
        </Badge>
      )}
      {ai.group === "2" && (
        <Badge tone="warn" icon={<ShieldAlert {...ICON} />}>
          Puede fallar
        </Badge>
      )}
      {ai.account === "no" && (
        <Badge tone="neutral" icon={<UserRound {...ICON} />}>
          Sin cuenta
        </Badge>
      )}
      {ai.account === "si" && (
        <Badge tone="neutral" icon={<UserRound {...ICON} />}>
          Pide cuenta
        </Badge>
      )}
      {lowCap && (
        <Badge tone="neutral" icon={<Gauge {...ICON} />}>
          Hasta {ai.daily_cap} al día
        </Badge>
      )}
    </div>
  );
}

function why(ai: CatalogAi): string {
  return [ai.may_fail, ai.note].filter(Boolean).join(" · ");
}

function CatalogCard({ ai, onConnect, onTeach, busy, defaultCap }: {
  ai: CatalogAi; onConnect: (key: string) => void; onTeach: (ai: CatalogAi) => void; busy: boolean; defaultCap: number;
}) {
  const label = ai.state === "no_funciona" ? "Probar otra vez" : "Conectar";
  return (
    <Card className="flex flex-col gap-3 p-5" data-catalog={ai.key}>
      <div className="flex items-center gap-3">
        <AiAvatar name={ai.key} label={ai.name} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[18px] font-semibold leading-tight">{ai.name}</p>
          <p className="truncate text-[15px] text-muted">{ai.by}</p>
        </div>
      </div>
      <p className="text-[16px] text-ink-2">{ai.purpose}</p>
      <Facts ai={ai} defaultCap={defaultCap} />
      {why(ai) && <p className="text-[15px] text-ink-2">{why(ai)}</p>}
      {ai.message && (
        <p className={`text-[15px] ${ai.state === "no_funciona" ? "text-bad-ink" : "text-ink-2"}`}>{ai.message}</p>
      )}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        <span className="min-w-0 truncate text-[15px] text-muted">{ai.url.replace(/^https:\/\//, "").replace(/\/$/, "")}</span>
        <div className="flex flex-wrap gap-2">
          {ai.state === "no_funciona" && (
            <Button variant="ghost" icon={<MousePointerClick size={18} aria-hidden />} disabled={busy} onClick={() => onTeach(ai)}>
              Enséñame esta web
            </Button>
          )}
          <Button variant="soft" icon={ai.state === "no_funciona" ? <RotateCcw size={18} aria-hidden /> : <Plug size={18} aria-hidden />} disabled={busy} onClick={() => onConnect(ai.key)}>
            {label}
          </Button>
        </div>
      </div>
    </Card>
  );
}

const RESULT: Record<BatchResult["status"], { icon: ReactNode; word: string }> = {
  pending: { icon: <span className="block h-5 w-5 rounded-full border-2 border-line-strong" aria-label="pendiente" />, word: "En cola" },
  running: { icon: <Loader2 size={20} className="animate-spin text-accent" aria-label="en marcha" />, word: "Probando" },
  ok: { icon: <CircleCheck size={20} className="text-ok-ink" aria-label="conectada" />, word: "Conectada" },
  sin_conectar: { icon: <CircleSlash size={20} className="text-ink-2" aria-label="sin conectar" />, word: "Sin conectar" },
  no_funciona: { icon: <CircleAlert size={20} className="text-bad-ink" aria-label="no funciona todavía" />, word: "No funciona todavía" },
  skipped: { icon: <CircleSlash size={20} className="text-muted" aria-label="no se probó" />, word: "No se probó" },
};

function BatchProgress({ b }: { b: Batch }) {
  return (
    <div className="flex flex-col gap-4">
      {b.message && (
        <p className={`rounded-xl px-4 py-3 text-[16px] ${b.status === "failed" ? "bg-bad-bg text-bad-ink" : "bg-surface-2 text-ink"}`}>{b.message}</p>
      )}
      {b.status !== "failed" && (
        <div>
          <div className="mb-1.5 flex justify-between text-[15px] text-ink-2">
            <span>
              {b.done} de {b.results.length} probadas
            </span>
            <span>{b.connected === 1 ? "1 conectada" : `${b.connected} conectadas`}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuemin={0} aria-valuemax={b.results.length} aria-valuenow={b.done}>
            <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(100 * b.done) / Math.max(1, b.results.length)}%` }} />
          </div>
        </div>
      )}
      <ol className="flex flex-col divide-y divide-line rounded-xl border border-line" aria-label="Resultado de cada IA">
        {b.results.map((r) => (
          <li key={r.key} className="px-4 py-3" data-result={r.key}>
            <div className="flex items-center gap-3">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center">{RESULT[r.status].icon}</span>
              <span className="flex-1 text-[16px] font-semibold">{r.name}</span>
              <span className="text-[15px] text-ink-2">{RESULT[r.status].word}</span>
            </div>
            {r.status === "running" && r.steps && (
              <ul className="ml-8 mt-1">
                {r.steps.map((s) => (
                  <StepRow key={s.step} step={s} />
                ))}
              </ul>
            )}
            {r.message && r.status !== "ok" && r.status !== "running" && <p className="ml-8 mt-1 text-[15px] text-ink-2">{r.message}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** "Conectar varias": all marked, as Iván asked; unmarking one means "no la quiero". Then the progress. */
function ConnectDialog({
  open,
  onOpenChange,
  choices,
  batch,
  onStart,
  onStop,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  choices: CatalogAi[];
  batch: Batch | null;
  onStart: (keys: string[], skip: string[]) => void;
  onStop: () => void;
}) {
  const [marked, setMarked] = useState<Set<string>>(new Set());
  // Everything marked when the list opens, and only then: the page refreshes every few seconds and must
  // never undo what Iván unmarked.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open && !wasOpen.current && !batch) setMarked(new Set(choices.filter((c) => c.state !== "no_la_quiero").map((c) => c.key)));
    wasOpen.current = open;
  }, [open, batch, choices]);
  const running = batch !== null && (batch.status === "permission" || batch.status === "running");
  const toggle = (key: string) =>
    setMarked((m) => {
      const n = new Set(m);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      wide
      title={batch ? "Conectando tus chats" : "Conectar varias"}
      description={
        batch
          ? "Se abren de una en una en la ventanita de webllm. Si una te pide entrar, entra tú: tienes 3 minutos por web."
          : "Vienen todas marcadas. Desmarca las que no quieras: quedarán como «No la quiero» y podrás conectarlas cuando quieras."
      }
    >
      {batch ? (
        <>
          <BatchProgress b={batch} />
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            {running ? (
              <Button variant="secondary" icon={<Square size={18} aria-hidden />} onClick={onStop}>
                Parar
              </Button>
            ) : (
              <Button variant="primary" onClick={() => onOpenChange(false)}>
                Cerrar
              </Button>
            )}
          </div>
        </>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            <Button size="sm" variant="ghost" onClick={() => setMarked(new Set(choices.map((c) => c.key)))}>
              Marcar todas
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMarked(new Set())}>
              Ninguna
            </Button>
          </div>
          <ul className="flex max-h-[52vh] flex-col divide-y divide-line overflow-y-auto rounded-xl border border-line">
            {choices.map((c) => (
              <li key={c.key}>
                <label className="flex cursor-pointer items-start gap-3 px-4 py-3 hover:bg-surface-2">
                  <input type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-[var(--accent)]" checked={marked.has(c.key)} onChange={() => toggle(c.key)} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[16px] font-semibold">
                      {c.name} <span className="font-normal text-muted">· {c.by}</span>
                    </span>
                    <span className="block text-[15px] text-ink-2">{c.purpose}</span>
                    {(!c.private || c.group === "2") && (
                      <span className="mt-1 block text-[15px] text-ink-2">
                        {!c.private && <b className="text-bad-ink">No privada: {c.note || "lo que escribes puede publicarse"}. </b>}
                        {c.group === "2" && <span>Puede fallar: {c.may_fail}.</span>}
                      </span>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[15px] text-ink-2">
            Chrome te pedirá permiso <b>una sola vez</b> para las marcadas. Cada una recibe un mensaje de prueba («pong»), que cuenta en su límite del día.
          </p>
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              icon={<Plug size={18} aria-hidden />}
              disabled={!marked.size}
              onClick={() => onStart([...marked], choices.filter((c) => !marked.has(c.key) && c.state !== "no_la_quiero").map((c) => c.key))}
            >
              {marked.size === 1 ? "Conectar 1" : `Conectar ${marked.size}`}
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}

const STATE_WORD: Record<CatalogAi["state"], string> = {
  conectada: "Conectada",
  sin_conectar: "Sin conectar",
  no_funciona: "No funciona todavía",
  no_la_quiero: "No la quiero",
};

/** The catalog table of docs/ESTADO.md, filled with what happened on this PC (PLAN-v5 F3, exit). */
function summary(cat: Catalogo): string {
  const rows = cat.ais.map((a) => `| ${a.name} | ${STATE_WORD[a.state]} | ${(a.message || "").replace(/\|/g, "/")} |`);
  return ["| IA | En mi PC | Por qué |", "|---|---|---|", ...rows].join("\n");
}

const SECTIONS: { state: CatalogAi["state"]; title: string }[] = [
  { state: "sin_conectar", title: "Sin conectar" },
  { state: "no_funciona", title: "No funcionan todavía" },
  { state: "no_la_quiero", title: "No las quieres" },
];

/**
 * "Conectores" (PLAN-v5 F3, like Settings → Connectors in ChatGPT or Claude): every web chat webllm knows.
 * Only the connected ones show in Open WebUI and in Preguntar.
 */
export function Conectores() {
  const { estado, refresh } = useStore();
  const toast = useToast();
  const openAdd = useOpenAddAi();
  const [cat, setCat] = useState<Catalogo | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [dialog, setDialog] = useState(false);
  const [teach, setTeach] = useState<CatalogAi | null>(null);
  const timer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const c = await api.catalogo();
      setCat(c);
      if (c.batch) setBatch(c.batch);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No pude leer la lista de chats.", "bad");
    }
  }, [toast]);
  useEffect(() => {
    load();
  }, [load]);

  // While "Conectar varias" runs, follow it; when it ends, refresh the lists.
  useEffect(() => {
    if (!batch || !(batch.status === "permission" || batch.status === "running")) return;
    timer.current = window.setTimeout(async () => {
      try {
        const b = await api.conectarVariasEstado(batch.batch_id);
        setBatch(b);
        if (b.status === "done" || b.status === "failed") {
          await Promise.all([load(), refresh()]);
        }
      } catch {
        setBatch({ ...batch });
      }
    }, EVERY_MS);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [batch, load, refresh]);

  const start = async (keys: string[], skip: string[] = []) => {
    try {
      setBatch(await api.conectarVarias(keys, skip));
      setDialog(true);
      await load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo empezar.", "bad");
    }
  };
  const stop = async () => {
    if (!batch) return;
    try {
      setBatch(await api.conectarVariasParar(batch.batch_id));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo parar.", "bad");
    }
  };

  const running = batch !== null && (batch.status === "permission" || batch.status === "running");
  const notConnected = cat?.ais.filter((a) => a.state !== "conectada" && !a.builtin) ?? [];
  const connected = (estado?.ais ?? []).filter((a) => a.kind === "chat");
  // the guard's usual daily cap: the one most chats have (a lower one shows on its card)
  const defaultCap = Math.max(0, ...(cat?.ais.map((a) => a.daily_cap) ?? [0]));
  return (
    <Page
      title="Conectores"
      subtitle={cat ? `${connected.length} conectados · ${notConnected.length} por conectar` : "Mirando la lista…"}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="lg" icon={<Plus size={20} aria-hidden />} onClick={openAdd}>
            Añadir otra IA
          </Button>
          <Button
            variant="primary"
            size="lg"
            icon={running ? <Loader2 size={20} className="animate-spin" aria-hidden /> : <Plug size={20} aria-hidden />}
            disabled={!running && !notConnected.length}
            onClick={() => {
              if (!running) setBatch(null);
              setDialog(true);
            }}
          >
            {running ? "Ver cómo va" : "Conectar varias"}
          </Button>
        </div>
      }
    >
      {estado && !estado.chrome && (
        <div className="mb-6">
          <Empty icon={<Globe size={26} />} title="Falta Chrome con la extensión" text="Para conectar chats hace falta Chrome abierto con la extensión webllm (0.6.0 o más nueva)." />
        </div>
      )}
      <p className="-mt-2 mb-8 max-w-3xl text-[16px] text-ink-2">
        Tus chats web. Solo los conectados salen en Open WebUI y en Preguntar. Conectar uno lo abre en la ventanita de webllm y le manda
        un mensaje de prueba; si pide entrar, entras tú.
      </p>
      <RepararCard />
      <section className="mb-10">
        <SectionTitle>Conectados</SectionTitle>
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {connected.map((ai) => (
            <AiCard key={ai.name} ai={ai} />
          ))}
        </div>
      </section>
      {cat &&
        SECTIONS.map(({ state, title }) => {
          const members = notConnected.filter((a) => a.state === state);
          if (!members.length) return null;
          return (
            <section key={state} className="mb-10">
              <SectionTitle>
                {title} ({members.length})
              </SectionTitle>
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {members.map((ai) => (
                  <CatalogCard key={ai.key} ai={ai} busy={running} defaultCap={defaultCap} onConnect={(key) => start([key])} onTeach={setTeach} />
                ))}
              </div>
            </section>
          );
        })}
      {cat && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-6">
          <p className="text-[15px] text-muted">
            Lista comprobada el {cat.checked.split("-").reverse().join("/")}. Si una web funciona con webllm solo se sabe al conectarla en tu PC.
          </p>
          <Button
            variant="ghost"
            icon={<ClipboardCopy size={18} aria-hidden />}
            onClick={() =>
              navigator.clipboard.writeText(summary(cat)).then(
                () => toast("Resumen copiado. Pégalo en el chat con Claude para apuntarlo en ESTADO."),
                () => toast("No se pudo copiar.", "bad"),
              )
            }
          >
            Copiar el resumen
          </Button>
        </div>
      )}
      <ConnectDialog open={dialog} onOpenChange={setDialog} choices={notConnected} batch={batch} onStart={start} onStop={stop} />
      {teach && <FichaDialog ai={teach.key} label={teach.name} open onOpenChange={(o) => { if (!o) { setTeach(null); load(); } }} />}
    </Page>
  );
}
