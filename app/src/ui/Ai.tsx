import { Check, Globe, Server } from "lucide-react";
import type { AiState } from "../api";

// Each AI gets its own color and monogram (white letters: >= 4.9:1 on every color).
const COLORS: Record<string, [string, string]> = {
  qwen: ["#5b4fd6", "#ffffff"],
  deepseek: ["#3d5ce0", "#ffffff"],
  "zai-chat": ["var(--ai-zai)", "var(--ai-zai-ink)"],
  zai: ["var(--ai-zai)", "var(--ai-zai-ink)"],
  meta: ["#0a5ce0", "#ffffff"],
  groq: ["#c2410c", "#ffffff"],
  nemotron: ["#4d7c0f", "#ffffff"],
};

function monogram(label: string) {
  const clean = label.replace(/\(.*\)/, "").trim();
  if (/^z\.ai/i.test(clean)) return "Z";
  const words = clean.split(/\s+/).filter(Boolean);
  return words.length > 1 ? (words[0][0] + words[1][0]).toUpperCase() : clean.slice(0, 1).toUpperCase();
}

export function AiAvatar({ name, label, size = 36 }: { name: string; label: string; size?: number }) {
  const [bg, ink] = COLORS[name] ?? ["#5f5f58", "#ffffff"];
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-xl font-bold ring-1 ring-line"
      style={{ width: size, height: size, background: bg, color: ink, fontSize: Math.max(15, size * 0.42) }}
    >
      {monogram(label)}
    </span>
  );
}

export function KindLabel({ kind }: { kind: "chat" | "api" }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-[15px] text-muted">
      {kind === "chat" ? <Globe size={15} aria-hidden /> : <Server size={15} aria-hidden />}
      {kind === "chat" ? "Chat en tu Chrome" : "Por API"}
    </span>
  );
}

const DOT: Record<AiState, string> = {
  lista: "var(--ok-dot)",
  saturada: "var(--warn-dot)",
  en_pausa: "var(--pause-dot)",
  sin_sesion: "var(--bad-dot)",
  sin_chrome: "var(--bad-dot)",
  apagada: "var(--bad-dot)",
};

/** A toggle chip to choose who gets the question. */
export function AiToggle({
  name,
  label,
  state,
  selected,
  onToggle,
}: {
  name: string;
  label: string;
  state: AiState;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      onClick={onToggle}
      className={
        "group inline-flex min-h-11 items-center gap-2 rounded-xl border py-1.5 pl-1.5 pr-3 text-[15px] font-semibold " +
        "cursor-pointer transition-colors duration-150 " +
        (selected
          ? "border-accent bg-accent-soft text-accent-soft-ink"
          : "border-line-strong bg-surface text-ink-2 hover:bg-surface-2")
      }
    >
      <AiAvatar name={name} label={label} size={30} />
      {label}
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: DOT[state] }} aria-hidden />
      <span className="sr-only">{state === "lista" ? "(conectada)" : "(con problemas)"}</span>
      <span
        aria-hidden
        className={
          "ml-0.5 flex h-5 w-5 items-center justify-center rounded-md border " +
          (selected ? "border-accent bg-accent text-accent-ink" : "border-line-strong")
        }
      >
        {selected && <Check size={14} strokeWidth={3} />}
      </span>
    </button>
  );
}
