import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, preguntar, type Estado, type FlowEvent } from "./api";

export interface TurnAnswer {
  target: string;
  label: string;
  phase: "waiting" | "asking" | "done";
  ok: boolean;
  text: string;
  seconds: number;
  error: string;
  code: string;
  provider: string;
  providerLabel: string;
  startedAt: number | null;
}

export interface Turn {
  id: string;
  title: string;
  prompt: string;
  /** The question this turn is about (for "Pásasela a…" it is the original question). */
  question: string;
  from?: { name: string; label: string; kind: "pasar" | "criticar" };
  answers: TurnAnswer[];
  runId: string | null;
  verified: boolean | null;
  running: boolean;
  error: { message: string; code: string } | null;
}

export interface AskOptions {
  prompt: string;
  to: string[];
  title?: string;
  question?: string;
  from?: Turn["from"];
  /** Called with the new turn's id as soon as it exists (to follow its progress). */
  onStart?: (id: string) => void;
}

interface Store {
  estado: Estado | null;
  offline: boolean;
  refresh: () => Promise<void>;
  turns: Turn[];
  ask: (o: AskOptions) => Promise<Turn>;
  labelOf: (name: string) => string;
}

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("StoreProvider missing");
  return s;
}

let counter = 0;

export function StoreProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [offline, setOffline] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const estadoRef = useRef<Estado | null>(null);

  const refresh = useCallback(async () => {
    try {
      const e = await api.estado();
      estadoRef.current = e;
      setEstado(e);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 4000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const labelOf = useCallback(
    (name: string) => estadoRef.current?.ais.find((a) => a.name === name)?.label ?? name,
    [],
  );

  const ask = useCallback(
    async (o: AskOptions): Promise<Turn> => {
      const id = `t${++counter}`;
      const turn: Turn = {
        id,
        title: o.title ?? "Pregunta",
        prompt: o.prompt,
        question: o.question ?? o.prompt,
        from: o.from,
        answers: o.to.map((name) => ({
          target: name,
          label: labelOf(name),
          phase: "waiting",
          ok: false,
          text: "",
          seconds: 0,
          error: "",
          code: "",
          provider: name,
          providerLabel: labelOf(name),
          startedAt: null,
        })),
        runId: null,
        verified: null,
        running: true,
        error: null,
      };
      setTurns((all) => [turn, ...all]);
      o.onStart?.(id);
      // Events arrive one after another, so this copy is always the latest state of the turn.
      let current = turn;
      const update = (fn: (t: Turn) => Turn) => {
        current = fn(current);
        const snapshot = current;
        setTurns((all) => all.map((t) => (t.id === id ? snapshot : t)));
      };
      const patchAnswer = (target: string, patch: Partial<TurnAnswer>) =>
        update((t) => ({ ...t, answers: t.answers.map((a) => (a.target === target ? { ...a, ...patch } : a)) }));

      const onEvent = (e: FlowEvent) => {
        if (e.type === "flow_start") update((t) => ({ ...t, runId: e.run_id }));
        else if (e.type === "target_start") patchAnswer(e.target, { phase: "asking", startedAt: Date.now() });
        else if (e.type === "target_done")
          patchAnswer(e.target, {
            phase: "done",
            ok: e.ok,
            text: e.text,
            seconds: e.seconds,
            error: e.error,
            code: e.code,
            provider: e.provider,
            providerLabel: e.provider_label,
          });
        else if (e.type === "flow_done") update((t) => ({ ...t, runId: e.run_id, verified: e.verified }));
        else if (e.type === "error") update((t) => ({ ...t, error: { message: e.error, code: e.code } }));
      };

      try {
        await preguntar({ prompt: o.prompt, to: o.to, title: o.title }, onEvent);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Algo salió mal al preguntar.";
        const code = err instanceof ApiError ? err.code : "error";
        update((t) => ({ ...t, error: { message, code } }));
      }
      // Anything still open when the stream ends did not get an answer.
      update((t) => ({
        ...t,
        running: false,
        answers: t.answers.map((a) =>
          a.phase === "done" ? a : { ...a, phase: "done", ok: false, error: a.error || "No llegó la respuesta.", code: a.code || "error" },
        ),
      }));
      refresh();
      return current;
    },
    [labelOf, refresh],
  );

  const value = useMemo(() => ({ estado, offline, refresh, turns, ask, labelOf }), [estado, offline, refresh, turns, ask, labelOf]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
