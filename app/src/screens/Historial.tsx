import { ArrowLeft, CircleCheck, CircleX, Copy, Download, History, Link2, Lock, LockOpen, MessageSquarePlus, Search, Workflow } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Ai, type HistoryAnswer, type RunDetail, type RunSummary } from "../api";
import { go } from "../nav";
import { useStore } from "../state";
import { AiAvatar } from "../ui/Ai";
import { Button, ButtonLink } from "../ui/Button";
import { Card } from "../ui/Card";
import { Empty } from "../ui/Empty";
import { Markdown } from "../ui/Markdown";
import { Modal } from "../ui/Modal";
import { Page } from "../ui/Page";
import { Badge, DoneBadge } from "../ui/Status";
import { useToast } from "../ui/Toast";
import { PassDialog } from "./Preguntar";

function when(ts: string | null) {
  if (!ts) return "";
  const d = new Date(ts);
  const today = new Date();
  const yesterday = new Date(Date.now() - 86400000);
  const time = d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === today.toDateString()) return `Hoy, ${time}`;
  if (d.toDateString() === yesterday.toDateString()) return `Ayer, ${time}`;
  return d.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: d.getFullYear() === today.getFullYear() ? undefined : "numeric" }) + `, ${time}`;
}

const shortTitle = (text: string) => (text.length > 90 ? `${text.slice(0, 90).trimEnd()}…` : text || "Pregunta");

/** Preview text without markdown marks (**, #, `, >). */
const plain = (text: string) => text.replace(/[*_`#>|]+/g, "").replace(/\s+/g, " ").trim();

export function LockBadge({ ok }: { ok: boolean }) {
  return ok ? (
    <Badge tone="ok" icon={<Lock size={16} aria-hidden />}>
      Intacto
    </Badge>
  ) : (
    <Badge tone="bad" icon={<LockOpen size={16} aria-hidden />}>
      Alterado
    </Badge>
  );
}

function RunRow({ run }: { run: RunSummary }) {
  return (
    <a
      href={`#/historial/${run.id}`}
      className="group flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4 shadow-card transition-colors duration-150 hover:border-line-strong hover:bg-surface-2 md:flex-row md:items-center md:gap-5 md:p-5"
    >
      <div className="flex shrink-0 items-center gap-2 md:w-44 md:flex-col md:items-start md:gap-1">
        <span className="text-[15px] font-semibold text-ink-2">{when(run.ts)}</span>
        <Badge tone="neutral" icon={run.kind === "cadena" ? <Workflow size={15} aria-hidden /> : <MessageSquarePlus size={15} aria-hidden />}>
          {run.kind === "cadena" ? "Cadena" : "Pregunta"}
        </Badge>
      </div>
      <div className="min-w-0 flex-1">
        {run.title !== "Pregunta" && <p className="font-semibold">{run.title}</p>}
        <p className="line-clamp-2 text-ink">{plain(run.text) || "(sin texto)"}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          {run.ais.map((a) => (
            <span key={a.name} className={`inline-flex items-center gap-1 text-[15px] ${a.ok ? "text-ok-ink" : "text-bad-ink"}`}>
              {a.ok ? <CircleCheck size={15} aria-hidden /> : <CircleX size={15} aria-hidden />}
              {a.label}
              <span className="sr-only">{a.ok ? "respondió" : "no respondió"}</span>
            </span>
          ))}
        </div>
      </div>
      <div className="shrink-0">
        <LockBadge ok={run.lock} />
      </div>
    </a>
  );
}

function HistoryList() {
  const [q, setQ] = useState("");
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    const t = window.setTimeout(async () => {
      try {
        const r = await api.historial(q.trim());
        if (alive) {
          setRuns(r.runs);
          setError("");
        }
      } catch (err) {
        if (alive) setError(err instanceof ApiError ? err.message : "No pude leer el historial.");
      }
    }, q ? 300 : 0);
    return () => {
      alive = false;
      window.clearTimeout(t);
    };
  }, [q]);

  return (
    <Page title="Historial" subtitle="Todo lo que has preguntado. El candado verde dice que nadie lo ha tocado desde que se guardó.">
      <div className="relative mb-6 max-w-2xl">
        <Search size={20} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar en preguntas y respuestas…"
          aria-label="Buscar en el historial"
          className="min-h-12 w-full rounded-xl border border-line-strong bg-surface pl-11 pr-4 text-[16px] text-ink placeholder:text-muted focus:border-accent focus:outline-none"
        />
      </div>
      {error && <p className="mb-4 text-bad-ink">{error}</p>}
      {runs && runs.length === 0 && !q && (
        <Empty icon={<History size={26} />} title="Aquí aparecerá todo lo que preguntes" text="Cada pregunta y cada respuesta se guarda en tu PC, con un candado que avisa si alguien la cambia.">
          <Button variant="primary" icon={<MessageSquarePlus size={18} aria-hidden />} onClick={() => go("preguntar")}>
            Hacer mi primera pregunta
          </Button>
        </Empty>
      )}
      {runs && runs.length === 0 && q && (
        <Empty icon={<Search size={26} />} title="No hay nada con esas palabras" text="Prueba con otra palabra, o borra la búsqueda para ver todo.">
          <Button variant="secondary" onClick={() => setQ("")}>
            Borrar la búsqueda
          </Button>
        </Empty>
      )}
      <div className="flex flex-col gap-3">{runs?.map((r) => <RunRow key={r.id} run={r} />)}</div>
    </Page>
  );
}

function HistoryAnswerCard({ a, onPass, question }: { a: HistoryAnswer; question: string; onPass: (a: HistoryAnswer) => void }) {
  const toast = useToast();
  const stopped = !a.ok && a.code === "cancelled";
  return (
    <Card className="flex min-w-0 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
        <AiAvatar name={a.provider} label={a.provider_label} size={36} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px] font-semibold">{a.provider_label}</p>
          {a.provider !== a.target && <p className="text-[15px] text-muted">en lugar de {a.label}</p>}
        </div>
        <DoneBadge ok={a.ok}>{a.ok ? `Respondió en ${a.seconds} s` : stopped ? "Parado por ti" : "No respondió"}</DoneBadge>
      </div>
      <div className="max-h-[560px] overflow-y-auto px-5 py-4">
        {a.ok ? <Markdown text={a.text} /> : <p className="text-bad-ink">{stopped ? "Lo has parado tú." : a.error || "No respondió."}</p>}
      </div>
      {a.ok && (
        <div data-footer className="flex flex-wrap gap-2 border-t border-line px-4 py-3">
          <Button size="sm" variant="secondary" icon={<Link2 size={18} aria-hidden />} onClick={() => onPass(a)} title={`Seguir con esta respuesta: ${question.slice(0, 60)}`}>
            Pásasela a otra IA
          </Button>
          <Button
            variant="ghost"
            icon={<Copy size={18} aria-hidden />}
            onClick={() => navigator.clipboard.writeText(a.text).then(() => toast("Respuesta copiada."), () => toast("No se pudo copiar.", "bad"))}
          >
            Copiar
          </Button>
        </div>
      )}
    </Card>
  );
}

function HistoryDetail({ id }: { id: string }) {
  const { estado } = useStore();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState("");
  const [choose, setChoose] = useState<HistoryAnswer | null>(null);
  const [pass, setPass] = useState<Parameters<typeof PassDialog>[0]["pass"]>(null);
  useEffect(() => {
    api.detalle(id).then(setRun, (err) => setError(err instanceof ApiError ? err.message : "No pude abrir este registro."));
  }, [id]);

  const pick = (to: Ai) => {
    if (!choose || !run) return;
    setPass({ kind: "pasar", to, from: { name: choose.provider, label: choose.provider_label }, question: run.text, answer: choose.text });
    setChoose(null);
  };

  return (
    <Page
      title={run ? (run.title === "Pregunta" ? shortTitle(plain(run.text)) : run.title) : "Registro"}
      subtitle={run ? `${run.kind === "cadena" ? "Cadena" : "Pregunta"} · ${when(run.ts)}` : undefined}
      action={
        run && (
          <ButtonLink variant="primary" size="lg" href={api.exportUrl(run.id)} icon={<Download size={20} aria-hidden />}>
            Exportar
          </ButtonLink>
        )
      }
    >
      <div className="mb-6">
        <Button variant="ghost" icon={<ArrowLeft size={18} aria-hidden />} onClick={() => go("historial")}>
          Volver al historial
        </Button>
      </div>
      {error && <p className="text-bad-ink">{error}</p>}
      {run && (
        <>
          <Card className={`mb-8 flex flex-wrap items-center gap-3 p-4 ${run.lock ? "" : "border-bad-ink"}`}>
            <LockBadge ok={run.lock} />
            <p className="flex-1 text-[15px] text-ink-2">
              {run.lock
                ? "Nadie ha cambiado este registro desde que se guardó: cada mensaje y cada respuesta coinciden con su huella."
                : "Algo de este registro se cambió después de guardarse, así que no te fíes de lo que ves aquí."}
            </p>
          </Card>
          {run.steps.map((s, i) => (
            <section key={s.id} className="mb-10">
              {run.steps.length > 1 && (
                <h2 className="mb-3 text-[19px] font-semibold">
                  Paso {i + 1}: {s.title}
                </h2>
              )}
              <div className="mb-4 rounded-2xl bg-surface-2 px-5 py-4">
                <p className="mb-1 text-[15px] font-semibold text-muted">Mensaje enviado</p>
                <p className="whitespace-pre-wrap">{s.message || "(este paso no llegó a enviarse)"}</p>
              </div>
              <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,440px),1fr))]">
                {s.answers.map((a) => (
                  <HistoryAnswerCard key={a.target} a={a} question={run.text} onPass={setChoose} />
                ))}
              </div>
            </section>
          ))}
          <p className="text-[15px] text-muted">Guardado en tu PC en: {run.folder}</p>
        </>
      )}
      {choose && (
        <ChooseAi
          ais={(estado?.ais ?? []).filter((a) => a.name !== choose.provider)}
          onPick={pick}
          onClose={() => setChoose(null)}
        />
      )}
      <PassDialog pass={pass} onClose={() => setPass(null)} />
    </Page>
  );
}

function ChooseAi({ ais, onPick, onClose }: { ais: Ai[]; onPick: (a: Ai) => void; onClose: () => void }) {
  return (
    <Modal open onOpenChange={(o) => !o && onClose()} title="¿A qué IA se la pasas?" description="Después podrás revisar el mensaje antes de enviarlo.">
      <div className="flex flex-col gap-1.5">
        {ais.map((a) => (
          <button
            key={a.name}
            type="button"
            onClick={() => onPick(a)}
            className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl px-3 text-left text-[16px] font-medium hover:bg-surface-2"
          >
            <AiAvatar name={a.name} label={a.label} size={30} />
            {a.label}
          </button>
        ))}
      </div>
    </Modal>
  );
}

export function Historial({ id }: { id?: string }) {
  return id ? <HistoryDetail id={id} /> : <HistoryList />;
}
