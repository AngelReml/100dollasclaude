import * as Menu from "@radix-ui/react-dropdown-menu";
import { Copy, Forward, Hand, History, Lightbulb, Lock, MessageSquareText, ScanSearch, Send, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Ai } from "../api";
import { go } from "../nav";
import { useStore, type Turn, type TurnAnswer } from "../state";
import { AiAvatar } from "../ui/Ai";
import { AiPicker } from "../ui/AiPicker";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Empty } from "../ui/Empty";
import { ProblemBox } from "../ui/Fix";
import { Markdown } from "../ui/Markdown";
import { Modal } from "../ui/Modal";
import { Page } from "../ui/Page";
import { Badge, DoneBadge, WorkingBadge } from "../ui/Status";
import { useToast } from "../ui/Toast";

const EXAMPLES = [
  "Explícame qué es la inflación como si tuviera 12 años.",
  "Dame 5 ideas de nombre para una cafetería pequeña de barrio y di por qué funciona cada una.",
  "Quiero aprender inglés en 3 meses. ¿Clases o una app? Dame un plan semana a semana.",
];

const PICKED_KEY = "webllm.elegidas";

function readPicked(): string[] | null {
  try {
    const v = JSON.parse(localStorage.getItem(PICKED_KEY) ?? "null");
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : null;
  } catch {
    return null;
  }
}

const short = (text: string, n = 240) => (text.length > n ? `${text.slice(0, n).trimEnd()}…` : text);

export function passMessage(kind: "pasar" | "criticar", fromLabel: string, question: string, answer: string) {
  if (kind === "pasar")
    return (
      `Otra IA (${fromLabel}) respondió esto a la pregunta «${short(question)}»:\n\n${answer}\n\n` +
      "¿Qué opinas? Si ves errores o algo mejorable, dame tu versión mejorada."
    );
  return (
    `Revisa con ojo crítico esta respuesta de ${fromLabel} a la pregunta «${short(question)}». ` +
    `Señala los errores, lo que falta y cómo la mejorarías.\n\nRESPUESTA:\n${answer}`
  );
}

function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [active]);
  return now;
}

/** Choose another AI, check the message, send it. Used by "Pásasela a…" and "Que la critique…". */
export function PassDialog({
  pass,
  onClose,
}: {
  pass: { kind: "pasar" | "criticar"; to: Ai; from: { name: string; label: string }; question: string; answer: string } | null;
  onClose: () => void;
}) {
  const { ask } = useStore();
  const [text, setText] = useState("");
  useEffect(() => {
    if (pass) setText(passMessage(pass.kind, pass.from.label, pass.question, pass.answer));
  }, [pass]);
  if (!pass) return null;
  const title = pass.kind === "pasar" ? `Pasar la respuesta a ${pass.to.label}` : `Que ${pass.to.label} la critique`;
  const send = () => {
    const runTitle = pass.kind === "pasar" ? `${pass.from.label} → ${pass.to.label}` : `${pass.to.label} critica a ${pass.from.label}`;
    ask({ prompt: text, to: [pass.to.name], title: runTitle, question: pass.question, from: { ...pass.from, kind: pass.kind } });
    onClose();
    go("preguntar");
  };
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onClose()}
      title={title}
      description={`Este es el mensaje que recibirá ${pass.to.label}. Puedes cambiarlo antes de enviarlo.`}
      wide
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={12}
        aria-label="Mensaje"
        className="w-full resize-y rounded-xl border border-line-strong bg-surface p-3 text-[16px] leading-relaxed text-ink focus:border-accent focus:outline-none"
      />
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
        <Button variant="primary" icon={<Send size={18} aria-hidden />} onClick={send} disabled={!text.trim()}>
          Enviar a {pass.to.label}
        </Button>
      </div>
    </Modal>
  );
}

function PassMenu({
  kind,
  exclude,
  onPick,
}: {
  kind: "pasar" | "criticar";
  exclude: string;
  onPick: (ai: Ai) => void;
}) {
  const { estado } = useStore();
  const others = (estado?.ais ?? []).filter((a) => a.name !== exclude);
  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <Button size="sm" variant="secondary" icon={kind === "pasar" ? <Forward size={18} aria-hidden /> : <ScanSearch size={18} aria-hidden />}>
          {kind === "pasar" ? "Pásasela a…" : "Que la critique…"}
        </Button>
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          align="start"
          sideOffset={6}
          className="animate-pop z-30 min-w-60 rounded-xl border border-line bg-surface p-1.5 shadow-pop"
        >
          <Menu.Label className="px-2.5 pb-1 pt-1.5 text-[15px] text-muted">
            {kind === "pasar" ? "¿A qué IA se la pasas?" : "¿Qué IA la critica?"}
          </Menu.Label>
          {others.map((a) => (
            <Menu.Item
              key={a.name}
              onSelect={() => onPick(a)}
              className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[15px] font-medium outline-none data-[highlighted]:bg-surface-2"
            >
              <AiAvatar name={a.name} label={a.label} size={26} />
              <span className="flex-1">{a.label}</span>
              {a.state !== "lista" && <span className="text-[15px] text-muted">(con problemas)</span>}
            </Menu.Item>
          ))}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

/** While one chat waits for Iván (verification, pop-up), the others are hidden and wait too. */
function waitingText(answer: TurnAnswer, ais: Ai[]): { mine: boolean; text: string } | null {
  if (answer.phase !== "asking") return null;
  const me = ais.find((a) => a.name === answer.target);
  if (me?.waiting === "challenge")
    return {
      mine: true,
      text: `${answer.label} pide una verificación. Resuélvela en la ventanita de webllm (ya la he puesto delante). Te espero hasta 5 minutos; después la respuesta llega sola, no hace falta volver a preguntar.`,
    };
  if (me?.waiting === "popup")
    return { mine: true, text: `${answer.label} ha sacado una ventana. Respóndela en la ventanita de webllm y sigo yo solo.` };
  if (me?.waiting === "hidden")
    return {
      mine: true,
      text: `La ventanita de webllm está tapada o minimizada, y ${answer.label} no escribe la respuesta mientras no se vea. Déjala a la vista (pequeña en una esquina vale): la respuesta sigue sola.`,
    };
  if (me?.waiting === "repair")
    return {
      mine: true,
      text: `La web de ${answer.label} ha cambiado y no encontraba lo que necesita. La estoy arreglando sin enviar nada; no tienes que hacer nada.`,
    };
  // a chat that webllm is repairing does not hold the others up
  const other = me?.kind === "chat" ? ais.find((a) => a.waiting && a.waiting !== "repair" && a.name !== answer.target) : undefined;
  if (other?.waiting === "hidden") return { mine: false, text: "La ventanita de webllm está tapada o minimizada: déjala a la vista y sigue sola." };
  if (other) return { mine: false, text: `Esperando a que termines con ${other.label} en la ventanita de webllm; después ${answer.label} sigue sola.` };
  return null;
}

function AnswerCard({ turn, answer, now, onPass }: { turn: Turn; answer: TurnAnswer; now: number; onPass: (kind: "pasar" | "criticar", to: Ai) => void }) {
  const { ask, estado, labelOf } = useStore();
  const waiting = waitingText(answer, estado?.ais ?? []);
  const toast = useToast();
  const elapsed = answer.startedAt ? Math.max(0, Math.round((now - answer.startedAt) / 1000)) : 0;
  const retry = () => ask({ prompt: turn.prompt, to: [answer.target], title: `${turn.title} (otra vez)`, question: turn.question, from: turn.from });
  const askOther = (other: string) =>
    ask({ prompt: turn.prompt, to: [other], title: `${turn.title} (a ${labelOf(other)})`, question: turn.question, from: turn.from });
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(answer.text);
      toast("Respuesta copiada.");
    } catch {
      toast("No se pudo copiar.", "bad");
    }
  };
  const replaced = answer.provider !== answer.target;
  return (
    <Card className="animate-pop flex min-w-0 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
        <AiAvatar name={answer.provider} label={answer.providerLabel} size={36} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px] font-semibold">{answer.providerLabel}</p>
          {replaced && <p className="text-[15px] text-muted">en lugar de {answer.label}</p>}
        </div>
        {answer.phase === "waiting" && <Badge tone="neutral" icon={<span className="animate-dot h-2 w-2 rounded-full bg-current" />}>En cola</Badge>}
        {answer.phase === "asking" &&
          (waiting?.mine ? (
            <Badge tone="warn" icon={<Hand size={16} aria-hidden />}>
              Te espera · {elapsed} s
            </Badge>
          ) : (
            <WorkingBadge>Esperando… {elapsed} s</WorkingBadge>
          ))}
        {answer.phase === "done" && (
          <DoneBadge ok={answer.ok}>{answer.ok ? `Respondió en ${answer.seconds} s` : "No respondió"}</DoneBadge>
        )}
      </div>
      <div className="max-h-[560px] min-h-28 flex-1 overflow-y-auto px-5 py-4 text-[16px]">
        {answer.phase !== "done" &&
          (waiting ? (
            <p className={waiting.mine ? "rounded-xl bg-warn-bg px-4 py-3 font-semibold text-warn-ink" : "text-ink-2"} role="status">
              {waiting.text}
            </p>
          ) : (
            <p className="text-ink-2">
              {answer.phase === "waiting" ? `En cola: le pregunto en cuanto termine la anterior.` : `${answer.label} está preparando la respuesta…`}
            </p>
          ))}
        {answer.phase === "done" && answer.ok && <Markdown text={answer.text} />}
        {answer.phase === "done" && !answer.ok && <ProblemBox code={answer.code} ai={answer.target} said={answer.error} onRetry={retry} onAskOther={askOther} />}
      </div>
      {answer.phase === "done" && answer.ok && (
        <div data-footer className="flex flex-wrap gap-2 border-t border-line px-4 py-3">
          <PassMenu kind="pasar" exclude={answer.provider} onPick={(ai) => onPass("pasar", ai)} />
          <PassMenu kind="criticar" exclude={answer.provider} onPick={(ai) => onPass("criticar", ai)} />
          <Button size="sm" variant="ghost" icon={<Copy size={18} aria-hidden />} onClick={copy}>
            Copiar
          </Button>
        </div>
      )}
    </Card>
  );
}

function TurnView({ turn, now, onPass }: { turn: Turn; now: number; onPass: (turn: Turn, a: TurnAnswer, kind: "pasar" | "criticar", to: Ai) => void }) {
  const [open, setOpen] = useState(false);
  const long = turn.prompt.length > 400;
  const answered = turn.answers.filter((a) => a.phase === "done" && a.ok).length;
  return (
    <section id={turn.id} className="animate-pop mb-10 scroll-mt-6">
      <div className="mb-4 rounded-2xl bg-surface-2 px-5 py-4">
        <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <MessageSquareText size={18} className="text-muted" aria-hidden />
          <p className="font-semibold">{turn.title}</p>
          <span className="text-[15px] text-muted">
            {turn.running
              ? `Esperando respuestas: ${answered} de ${turn.answers.length}`
              : `${answered} de ${turn.answers.length} respondieron`}
          </span>
          {!turn.running && turn.verified && (
            <span className="inline-flex items-center gap-1 text-[15px] text-ok-ink">
              <Lock size={15} aria-hidden /> Guardado en el historial, con candado verde
            </span>
          )}
        </div>
        <p className="whitespace-pre-wrap text-[16px]">{long && !open ? short(turn.prompt, 400) : turn.prompt}</p>
        {long && (
          <button type="button" onClick={() => setOpen(!open)} className="mt-1 cursor-pointer text-[15px] font-semibold text-accent-soft-ink underline underline-offset-2 dark:text-accent">
            {open ? "Ver menos" : "Ver el mensaje entero"}
          </button>
        )}
      </div>
      {turn.error && (
        <div className="mb-4">
          <ProblemBox code={turn.error.code} ai={turn.answers[0]?.target ?? ""} />
        </div>
      )}
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,440px),1fr))]">
        {turn.answers.map((a) => (
          <AnswerCard key={a.target} turn={turn} answer={a} now={now} onPass={(kind, to) => onPass(turn, a, kind, to)} />
        ))}
      </div>
    </section>
  );
}

export function Preguntar() {
  const { estado, turns, ask } = useStore();
  const toast = useToast();
  const [text, setText] = useState("");
  const [picked, setPickedState] = useState<string[] | null>(readPicked);
  const [pass, setPass] = useState<Parameters<typeof PassDialog>[0]["pass"]>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const ais = estado?.ais ?? [];
  // The last choice is remembered; the first time, every AI that is ready is ticked.
  const selected = useMemo(() => {
    const names = ais.map((a) => a.name);
    return picked ? picked.filter((n) => names.includes(n)) : ais.filter((a) => a.state === "lista").map((a) => a.name);
  }, [picked, ais]);
  const setPicked = (names: string[]) => {
    setPickedState(names);
    try {
      localStorage.setItem(PICKED_KEY, JSON.stringify(names));
    } catch {
      // not remembered: the default choice comes back next time
    }
  };
  const running = turns.some((t) => t.running);
  const now = useNow(running);

  useEffect(() => box.current?.focus(), []);

  const chats = ais.filter((a) => a.kind === "chat" && selected.includes(a.name)).length;

  const send = (prompt = text) => {
    if (!prompt.trim()) return;
    if (!selected.length) {
      toast("Elige al menos una IA.", "bad");
      return;
    }
    const order = ais.map((a) => a.name).filter((n) => selected.includes(n));
    ask({
      prompt: prompt.trim(),
      to: order,
      onStart: (id) => requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })),
    });
    setText("");
  };

  return (
    <Page title="Preguntar" subtitle="Escribe una vez y elige a quién. Las respuestas salen una al lado de otra.">
      <Card className="mb-10 p-5 md:p-6">
        <label htmlFor="pregunta" className="mb-2 block text-[17px] font-semibold">
          Tu pregunta
        </label>
        <textarea
          id="pregunta"
          ref={box}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              send();
            }
          }}
          rows={4}
          placeholder="Escribe aquí lo que quieras preguntar…"
          className="w-full resize-y rounded-xl border border-line-strong bg-surface p-3.5 text-[17px] leading-relaxed text-ink placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <p className="text-[17px] font-semibold">¿A quién?</p>
          <AiPicker ais={ais} selected={selected} onChange={setPicked} />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[15px] text-muted">
            {chats > 0
              ? `Gasta 1 mensaje de cada chat elegido (${chats}). Las IAs por API y las de tu PC no gastan tus chats.`
              : "No gasta mensajes de tus chats."}{" "}
            Atajo: Ctrl + Enter.
          </p>
          <Button variant="primary" size="lg" icon={<Send size={20} aria-hidden />} onClick={() => send()} disabled={!text.trim() || !selected.length}>
            Preguntar{selected.length ? ` a ${selected.length === ais.length ? "todas" : selected.length}` : ""}
          </Button>
        </div>
      </Card>

      {turns.length === 0 ? (
        <Empty
          icon={<Sparkles size={26} />}
          title="Pregunta lo mismo a todas tus IAs a la vez"
          text="Verás las respuestas una al lado de otra. Luego puedes pasarle una respuesta a otra IA para que la mejore o la critique."
        >
          <p className="mb-1 font-semibold">Prueba con uno de estos ejemplos:</p>
          {EXAMPLES.map((ex) => (
            <div key={ex} className="flex w-full max-w-2xl flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-left">
              <span className="flex min-w-0 flex-1 items-start gap-2">
                <Lightbulb size={18} className="mt-1 shrink-0 text-muted" aria-hidden />
                {ex}
              </span>
              <Button variant="soft" onClick={() => send(ex)} disabled={!selected.length}>
                Probar este ejemplo
              </Button>
            </div>
          ))}
        </Empty>
      ) : (
        <>
          {turns.map((t) => (
            <TurnView
              key={t.id}
              turn={t}
              now={now}
              onPass={(turn, a, kind, to) => setPass({ kind, to, from: { name: a.provider, label: a.providerLabel }, question: turn.question, answer: a.text })}
            />
          ))}
          <div className="flex justify-center">
            <Button variant="ghost" icon={<History size={18} aria-hidden />} onClick={() => go("historial")}>
              Ver todo lo que has preguntado antes
            </Button>
          </div>
        </>
      )}
      <PassDialog pass={pass} onClose={() => setPass(null)} />
    </Page>
  );
}
