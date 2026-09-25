import { CircleAlert, CircleCheck, CirclePause, Clock3, Loader2, PlugZap, Power, UserRoundX } from "lucide-react";
import type { ReactNode } from "react";
import type { AiState } from "../api";

export type Tone = "ok" | "warn" | "pause" | "bad" | "neutral" | "busy";

const tones: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok-ink",
  warn: "bg-warn-bg text-warn-ink",
  pause: "bg-pause-bg text-pause-ink",
  bad: "bg-bad-bg text-bad-ink",
  neutral: "bg-surface-2 text-ink-2",
  busy: "bg-accent-soft text-accent-soft-ink",
};

/** Traffic light: color + icon + word, so it never depends on color alone. */
export function Badge({ tone, icon, children }: { tone: Tone; icon: ReactNode; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[15px] font-semibold ${tones[tone]}`}>
      {icon}
      {children}
    </span>
  );
}

const ICON = { size: 16, strokeWidth: 2.25, "aria-hidden": true } as const;

export const AI_STATE: Record<AiState, { tone: Tone; word: string; icon: ReactNode }> = {
  lista: { tone: "ok", word: "Conectada", icon: <CircleCheck {...ICON} /> },
  saturada: { tone: "warn", word: "Saturada", icon: <Clock3 {...ICON} /> },
  en_pausa: { tone: "pause", word: "En pausa", icon: <CirclePause {...ICON} /> },
  sin_sesion: { tone: "bad", word: "Sin sesión", icon: <UserRoundX {...ICON} /> },
  sin_chrome: { tone: "bad", word: "Falta Chrome", icon: <PlugZap {...ICON} /> },
  apagada: { tone: "bad", word: "Apagada", icon: <Power {...ICON} /> },
};

export function AiStateBadge({ state }: { state: AiState }) {
  const s = AI_STATE[state];
  return (
    <Badge tone={s.tone} icon={s.icon}>
      {s.word}
    </Badge>
  );
}

export function WorkingBadge({ children }: { children: ReactNode }) {
  return (
    <Badge tone="busy" icon={<Loader2 {...ICON} className="animate-spin" />}>
      {children}
    </Badge>
  );
}

export function DoneBadge({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <Badge tone={ok ? "ok" : "bad"} icon={ok ? <CircleCheck {...ICON} /> : <CircleAlert {...ICON} />}>
      {children}
    </Badge>
  );
}
