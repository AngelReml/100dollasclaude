import { Pencil, RotateCcw, Scale, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Comite, type ComiteRole } from "../api";
import { Button } from "./Button";
import { Card } from "./Card";
import { Modal } from "./Modal";
import { useToast } from "./Toast";

/**
 * The Committee (PLAN-v5 F7): it runs in Open WebUI ("webllm · Comité"); here Iván sees who would take part right
 * now and changes what is his to change: how many, "pensar", two web chats at once (off: never tried on his PC), and
 * the roles, kept as templates.
 */
export function ComiteCard() {
  const toast = useToast();
  const [c, setC] = useState<Comite | null>(null);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    api.comite().then(setC, () => setC(null));
  }, []);
  if (!c) return null;
  const save = async (body: Parameters<typeof api.guardarComite>[0], done: string) => {
    try {
      setC(await api.guardarComite(body));
      toast(done);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo guardar.", "bad");
    }
  };
  const p = c.preview;
  return (
    <Card className="flex flex-col gap-5 p-6" data-card="comite">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-[18px] font-semibold">
            <Scale size={20} aria-hidden /> El Comité
          </h3>
          <p className="mt-1 max-w-[70ch] text-[15px] text-ink-2">
            En Open WebUI elige <b>webllm · Comité</b> y escribe tu idea. Antes de enviar nada te dice quién participa, con qué
            rol y cuánto gasta de cada cuenta; solo empieza cuando escribes «adelante».
          </p>
        </div>
        <div className="flex gap-1 rounded-xl bg-surface-2 p-1" role="radiogroup" aria-label="Cuántas IAs">
          {([3, 5] as const).map((n) => (
            <button key={n} type="button" role="radio" aria-checked={c.number === n}
              className={`min-h-10 rounded-lg px-4 text-[15px] font-semibold ${c.number === n ? "bg-surface text-ink shadow-card" : "text-ink-2"}`}
              onClick={() => save({ number: n }, `El Comité será de ${n}.`)}>
              {n} IAs
            </button>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-2 flex items-center gap-2 text-[15px] font-semibold"><Users size={17} aria-hidden /> Si lo lanzas ahora</p>
        {p ? (
          <ol className="grid gap-1.5 text-[15px] md:grid-cols-2">
            {p.seats.map((s, i) => (
              <li key={s.provider}>
                {i + 1}. <b>{s.label}</b> · {s.role?.name}
                {s.model ? <span className="text-ink-2"> · {s.model}{s.modes.length ? " con «pensar»" : ""}</span> : null}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[15px] text-bad-ink">{c.preview_error}</p>
        )}
        {p && (
          <p className="mt-2 text-[15px] text-ink-2">
            {p.reserves.length ? <>Reservas: {p.reserves.map((s) => s.label).join(", ")}. </> : null}
            Fusión: {p.fusion[0]?.label}.
            {p.missing.length ? <> No entran: {grouped(p.missing)}.</> : null}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-3">
        <label className="flex cursor-pointer items-center gap-3 text-[16px]">
          <input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={c.think}
            onChange={(e) => save({ think: e.target.checked }, e.target.checked ? "Los chats web usarán «pensar» si lo tienen." : "Sin «pensar».")} />
          Los chats web, con «pensar» si lo tienen
        </label>
        <label className="flex cursor-pointer items-start gap-3 text-[16px]">
          <input type="checkbox" className="mt-0.5 h-5 w-5 accent-[var(--accent)]" checked={c.parallel_web}
            onChange={(e) => save({ parallel_web: e.target.checked }, e.target.checked ? "Dos chats web a la vez: encendido." : "Los chats web, de uno en uno.")} />
          <span>
            Dos chats web a la vez
            <span className="block text-[15px] text-ink-2">Más rápido, pero todavía sin probar en tu PC: déjalo apagado hasta que lo probemos juntos.</span>
          </span>
        </label>
      </div>
      <div>
        <p className="mb-2 text-[15px] font-semibold">Roles</p>
        <ol className="grid gap-1.5 text-[15px] md:grid-cols-2">
          {c.roles.slice(0, c.number).map((r, i) => (
            <li key={r.name}>{i + 1}. <b>{r.name}</b>: <span className="text-ink-2">{r.asks}</span></li>
          ))}
        </ol>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="soft" icon={<Pencil size={18} aria-hidden />} onClick={() => setEditing(true)}>Cambiar los roles</Button>
          <Button variant="ghost" icon={<RotateCcw size={18} aria-hidden />} onClick={() => save({ reset_roles: true }, "Vuelven los roles de webllm.")}>
            Volver a los de webllm
          </Button>
        </div>
      </div>
      {editing && <RolesDialog roles={c.roles} onClose={() => setEditing(false)} onSave={(roles) => save({ roles }, "Roles guardados.").then(() => setEditing(false))} />}
    </Card>
  );
}

/** "sin conectar: Kimi, Duck.ai; sin configurar: GLM-5.2 (API); DeepSeek (está en pausa)", as the plan says it. */
function grouped(missing: [string, string][]): string {
  const by = new Map<string, string[]>();
  for (const [name, why] of missing) by.set(why, [...(by.get(why) ?? []), name]);
  return [...by.entries()]
    .map(([why, names]) => (why === "sin conectar" || why === "sin configurar" ? `${why}: ${names.join(", ")}` : names.map((n) => `${n} (${why})`).join("; ")))
    .join("; ");
}

function RolesDialog({ roles, onClose, onSave }: { roles: ComiteRole[]; onClose: () => void; onSave: (r: ComiteRole[]) => void }) {
  const [draft, setDraft] = useState<ComiteRole[]>(roles.map((r) => ({ ...r })));
  const set = (i: number, key: keyof ComiteRole, value: string) => setDraft(draft.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
  return (
    <Modal open onOpenChange={(o) => !o && onClose()} title="Los roles del Comité"
      description="Con 3 IAs van los tres primeros. Cada rol: su nombre y qué mira.">
      <div className="flex flex-col gap-4">
        {draft.map((r, i) => (
          <div key={i} className="grid gap-2 md:grid-cols-[200px_1fr]">
            <input aria-label={`Nombre del rol ${i + 1}`} className="min-h-11 rounded-xl border border-line-strong bg-surface px-3 text-[16px]"
              value={r.name} maxLength={60} onChange={(e) => set(i, "name", e.target.value)} />
            <input aria-label={`Qué mira el rol ${i + 1}`} className="min-h-11 rounded-xl border border-line-strong bg-surface px-3 text-[16px]"
              value={r.asks} maxLength={300} onChange={(e) => set(i, "asks", e.target.value)} />
          </div>
        ))}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button variant="primary" onClick={() => onSave(draft)}>Guardar los roles</Button>
        </div>
      </div>
    </Modal>
  );
}
