import { Cpu, Globe, Server } from "lucide-react";
import { api, type AiState } from "../api";
import { useStore } from "../state";

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

// Local models take their server's color (name "lmstudio:<model>", "ollama:<model>").
const SERVER_COLORS: Record<string, [string, string]> = {
  lmstudio: ["#6d28d9", "#ffffff"],
  ollama: ["#0f766e", "#ffffff"],
};

function colorsFor(name: string): [string, string] {
  const server = name.includes(":") ? name.split(":", 1)[0] : "";
  return COLORS[name] ?? SERVER_COLORS[server] ?? ["#5f5f58", "#ffffff"];
}

function monogram(label: string) {
  if (/^LM Studio/i.test(label)) return "LM";
  if (/^Ollama/i.test(label)) return "OL";
  const clean = label.split(" · ")[0].replace(/\(.*\)/, "").trim();
  if (/^z\.ai/i.test(clean)) return "Z";
  const words = clean.split(/\s+/).filter(Boolean);
  return words.length > 1 ? (words[0][0] + words[1][0]).toUpperCase() : clean.slice(0, 1).toUpperCase();
}

export function AiAvatar({ name, label, size = 36 }: { name: string; label: string; size?: number }) {
  const { estado } = useStore();
  const [bg, ink] = colorsFor(name);
  if (estado?.ais.some((a) => a.name === name && a.icon)) {
    // The site's own icon (sites added from the app), on white so dark icons stay visible in dark mode.
    return (
      <span aria-hidden className="inline-flex shrink-0 items-center justify-center rounded-xl bg-white ring-1 ring-line" style={{ width: size, height: size }}>
        <img src={api.iconUrl(name)} alt="" width={Math.round(size * 0.62)} height={Math.round(size * 0.62)} className="object-contain" />
      </span>
    );
  }
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

export const KIND_TEXT: Record<"chat" | "api" | "local", string> = {
  chat: "Chat en tu Chrome",
  api: "Por API",
  local: "En tu PC",
};

export function KindLabel({ kind }: { kind: "chat" | "api" | "local" }) {
  const Icon = kind === "chat" ? Globe : kind === "api" ? Server : Cpu;
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-[15px] text-muted">
      <Icon size={15} aria-hidden />
      {KIND_TEXT[kind]}
    </span>
  );
}

export const DOT: Record<AiState, string> = {
  lista: "var(--ok-dot)",
  saturada: "var(--warn-dot)",
  en_pausa: "var(--pause-dot)",
  sin_sesion: "var(--bad-dot)",
  sin_chrome: "var(--bad-dot)",
  apagada: "var(--bad-dot)",
};
