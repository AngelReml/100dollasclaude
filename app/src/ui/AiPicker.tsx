import * as Menu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";
import type { Ai, AiState } from "../api";
import { AiAvatar, DOT, KIND_TEXT } from "./Ai";

const GROUPS: { kind: Ai["kind"]; title: string }[] = [
  { kind: "chat", title: "Chats en tu Chrome" },
  { kind: "api", title: "IAs por API" },
  { kind: "local", title: KIND_TEXT.local },
];

const WHY: Record<AiState, string> = {
  lista: "",
  saturada: "saturada",
  en_pausa: "en pausa",
  sin_sesion: "sin sesión",
  sin_chrome: "falta Chrome",
  apagada: "apagada",
};

const itemClass =
  "flex min-h-11 cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-[15px] font-medium outline-none data-[highlighted]:bg-surface-2";

/**
 * Who gets the question: one button ("IAs: 3 elegidas") that opens a list with tick boxes,
 * grouped by kind. The list stays open while ticking; Esc or a click outside closes it.
 * The same piece will choose the AIs of each card in the Mesa (phase 4).
 */
export function AiPicker({ ais, selected, onChange }: { ais: Ai[]; selected: string[]; onChange: (names: string[]) => void }) {
  const chosen = ais.filter((a) => selected.includes(a.name));
  const text =
    chosen.length === 0 ? "Elige a qué IAs" : chosen.length === ais.length ? `IAs: todas (${ais.length})` : `IAs: ${chosen.length} elegida${chosen.length > 1 ? "s" : ""}`;
  const toggle = (name: string) => onChange(selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name]);
  const keepOpen = (e: Event) => e.preventDefault();
  const shortcuts: { text: string; pick: () => string[] }[] = [
    { text: "Todas las listas", pick: () => ais.filter((a) => a.state === "lista").map((a) => a.name) },
    { text: "Solo las que no gastan cuenta", pick: () => ais.filter((a) => a.kind !== "chat" && a.state === "lista").map((a) => a.name) },
    { text: "Ninguna", pick: () => [] },
  ];

  return (
    <Menu.Root modal={false}>
      <Menu.Trigger asChild>
        <button
          type="button"
          className="inline-flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-line-strong bg-surface py-1.5 pl-2 pr-3.5 text-[16px] font-semibold text-ink transition-colors duration-150 hover:bg-surface-2"
        >
          <span className="flex items-center -space-x-1" aria-hidden>
            {chosen.slice(0, 4).map((a) => (
              <span key={a.name} className="rounded-xl ring-2 ring-surface">
                <AiAvatar name={a.name} label={a.label} size={30} />
              </span>
            ))}
            {chosen.length > 4 && (
              <span className="flex h-[30px] min-w-[30px] items-center justify-center rounded-xl bg-surface-2 px-1.5 text-[15px] font-semibold text-ink-2 ring-2 ring-surface">
                +{chosen.length - 4}
              </span>
            )}
          </span>
          {text}
          <ChevronDown size={18} className="text-muted" aria-hidden />
        </button>
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          align="start"
          sideOffset={6}
          collisionPadding={16}
          className="animate-pop z-30 max-h-[min(560px,var(--radix-dropdown-menu-content-available-height))] w-[min(380px,calc(100vw-32px))] overflow-y-auto rounded-xl border border-line bg-surface p-1.5 shadow-pop"
        >
          <div className="flex flex-wrap gap-1.5 px-1 pb-1.5 pt-1">
            {shortcuts.map((s) => (
              <Menu.Item
                key={s.text}
                onSelect={(e) => {
                  keepOpen(e);
                  onChange(s.pick());
                }}
                className="cursor-pointer rounded-lg bg-surface-2 px-2.5 py-1.5 text-[15px] font-semibold text-ink-2 outline-none data-[highlighted]:bg-accent-soft data-[highlighted]:text-accent-soft-ink"
              >
                {s.text}
              </Menu.Item>
            ))}
          </div>
          {GROUPS.map((g) => {
            const members = ais.filter((a) => a.kind === g.kind);
            if (!members.length) return null;
            return (
              <Menu.Group key={g.kind}>
                <Menu.Separator className="my-1 h-px bg-line" />
                <Menu.Label className="px-2.5 pb-1 pt-1.5 text-[15px] font-semibold text-muted">{g.title}</Menu.Label>
                {members.map((a) => (
                  <Menu.CheckboxItem
                    key={a.name}
                    checked={selected.includes(a.name)}
                    onSelect={keepOpen}
                    onCheckedChange={() => toggle(a.name)}
                    className={itemClass}
                  >
                    <span
                      aria-hidden
                      className={
                        "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border " +
                        (selected.includes(a.name) ? "border-accent bg-accent text-accent-ink" : "border-line-strong")
                      }
                    >
                      <Menu.ItemIndicator>
                        <Check size={14} strokeWidth={3} />
                      </Menu.ItemIndicator>
                    </span>
                    <AiAvatar name={a.name} label={a.label} size={28} />
                    <span className="min-w-0 flex-1 truncate">{a.label}</span>
                    <span className="inline-flex shrink-0 items-center gap-1.5 text-[15px] text-muted">
                      {WHY[a.state]}
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: DOT[a.state] }} aria-hidden />
                    </span>
                  </Menu.CheckboxItem>
                ))}
              </Menu.Group>
            );
          })}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
