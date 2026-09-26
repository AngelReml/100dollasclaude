import { Crown, FileUp, Hand, ListChecks, Loader2, Menu, MousePointerClick, ScanSearch, Sparkles, ToggleRight, Undo2, Wrench } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type Ficha, type SiteCheck } from "../api";
import { Button } from "./Button";
import { Modal } from "./Modal";
import { Badge } from "./Status";
import { useToast } from "./Toast";

const ICON = { size: 16, strokeWidth: 2.25, "aria-hidden": true } as const;

/** What the daily check found (PLAN-v5 F6), in Iván's words. */
export function checkWords(c: SiteCheck): string {
  const words: Record<SiteCheck["state"], string> = {
    bien: "funciona",
    reparada: `funciona: su web había cambiado y la arregló ${c.repaired_by ?? "una IA"}, sin enviar nada`,
    sin_sesion: "no tiene la sesión abierta (pulsa Conectar y entra)",
    verificacion: "pedía una verificación",
    saturada: "estaba saturada (no es cosa de tu cuenta)",
    limite: "había llegado a su límite",
    bloqueada: "la cuenta parecía bloqueada",
    no_encuentro_la_caja: "no encontré su caja de texto: enséñamela con «Enséñame esta web»",
    no_se_pudo_abrir: "no se pudo abrir",
  };
  return words[c.state] ?? c.state;
}

const TEACH_STEPS: { what: "input" | "send" | "answer"; text: string }[] = [
  { what: "input", text: "Paso 1 de 3: en la ventanita de webllm, haz clic en la caja donde se escribe." },
  { what: "send", text: "Paso 2 de 3: ahora haz clic en su botón de enviar (no se enviará nada)." },
  { what: "answer", text: "Paso 3 de 3: y ahora haz clic en la última respuesta de la IA." },
];

/** "2026-09-26 06:05" → "26/09/2026 a las 06:05". */
export function readable(when: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})/.exec(when);
  return m ? `${m[3]}/${m[2]}/${m[1]} a las ${m[4]}` : when;
}

function Block({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="flex items-center gap-2 text-[16px] font-semibold">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  );
}

/**
 * A chat's card (PLAN-v5 F4, D22): what webllm read on its page, read-only. Its models with the strongest
 * marked (from the catalog's table, or Iván's choice), its modes, its "+" menu, what files it takes.
 * "Enséñame dónde está" when webllm cannot find the model selector or the "+".
 */
export function FichaDialog({ ai, label, open, onOpenChange }: { ai: string; label: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const toast = useToast();
  const [f, setF] = useState<Ficha | null>(null);
  const [busy, setBusy] = useState<"" | "descubrir" | "model" | "plus" | "teach">("");
  const [step, setStep] = useState<number | null>(null);
  const load = useCallback(async () => {
    try {
      setF(await api.ficha(ai));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No pude leer la ficha.", "bad");
    }
  }, [ai, toast]);
  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const run = async (what: "descubrir" | "model" | "plus", fn: () => Promise<Ficha>, done: string) => {
    setBusy(what);
    try {
      setF(await fn());
      toast(done);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo.", "bad");
    } finally {
      setBusy("");
    }
  };
  // "Enséñame esta web" (PLAN-v5 F6, layer 4): three clicks in its window, each tried on the page, nothing sent.
  const teachWeb = async () => {
    setBusy("teach");
    try {
      for (let i = 0; i < TEACH_STEPS.length; i++) {
        setStep(i);
        setF(await api.ensename(ai, TEACH_STEPS[i].what));
      }
      toast(`Aprendido: la caja, el botón de enviar y la respuesta de ${label}. Ya puedes preguntarle.`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo.", "bad");
    } finally {
      setStep(null);
      setBusy("");
    }
  };
  const undo = (index: number) => run("descubrir", () => api.fichaDeshacer(ai, index), "Deshecho: webllm ya no lo usa.");
  const mark = (model: string | null) =>
    run("descubrir", () => api.fichaPotente(ai, model), model ? `«${model}» es ahora el más potente de ${label}.` : "Vuelve a mandar la tabla de webllm.");

  return (
    <Modal open={open} onOpenChange={onOpenChange} wide title={`Ficha de ${label}`}
      description="Lo que webllm leyó en su web: abre sus menús, los lee y los cierra. No pulsa ninguna opción ni envía nada.">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" icon={busy === "descubrir" ? <Loader2 size={18} className="animate-spin" aria-hidden /> : <ScanSearch size={18} aria-hidden />}
            disabled={!!busy} onClick={() => run("descubrir", () => api.descubrir(ai), "Ficha leída en su web.")}>
            {busy === "descubrir" ? "Leyendo su web…" : f?.discovered ? "Descubrir otra vez" : "Descubrir"}
          </Button>
          <span className="text-[15px] text-muted">{f?.when ? `Leída el ${readable(f.when)}.` : "Todavía no la has leído."}</span>
        </div>

        {f?.discovered && (
          <>
            <Block icon={<Crown size={18} aria-hidden />} title="Modelos">
              {f.models.length ? (
                <ul className="flex flex-col divide-y divide-line rounded-xl border border-line">
                  {f.models.map((m) => (
                    <li key={m.slug} className="flex flex-wrap items-center gap-3 px-4 py-2.5" data-model={m.name}>
                      <span className="min-w-0 flex-1 text-[16px] font-semibold">{m.name}</span>
                      {m.strongest && (
                        <Badge tone="ok" icon={<Crown {...ICON} />}>
                          {m.by_ivan ? "El más potente (tú)" : "El más potente"}
                        </Badge>
                      )}
                      {m.tie && (
                        <Badge tone="warn" icon={<Sparkles {...ICON} />}>
                          Empate: dime cuál
                        </Badge>
                      )}
                      {!m.known && (
                        <Badge tone="neutral" icon={<Sparkles {...ICON} />}>
                          Nuevo, sin datos
                        </Badge>
                      )}
                      {!m.strongest && (
                        <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => mark(m.name)}>
                          Este es el más potente
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[15px] text-ink-2">No encontré su selector de modelos.</p>
              )}
              <p className="text-[15px] text-muted">
                {f.use_page_model
                  ? "Sin elegir modelo, webllm usa el que tenga puesto su web (lo elegiste tú): no lo cambia."
                  : f.strongest
                    ? `Sin elegir modelo, webllm usa «${f.strongest}».`
                    : "No sé cuál es el más potente: webllm usa el que tenga puesto su web hasta que me lo digas."}
                {f.table.source ? ` Orden según ${f.table.source} (${f.table.checked}).` : ""}
                {(f.strongest_by_ivan || f.use_page_model) && (
                  <>
                    {" "}
                    <button type="button" className="cursor-pointer font-semibold text-accent-soft-ink underline" onClick={() => mark(null)}>
                      Volver a la tabla de webllm
                    </button>
                  </>
                )}
              </p>
              {!f.use_page_model && f.models.length > 0 && (
                <div>
                  <Button size="sm" variant="ghost" disabled={!!busy}
                    onClick={() => run("descubrir", () => api.fichaPotente(ai, null, true), `${label} usará siempre el modelo que tenga puesto su web.`)}>
                    Usar siempre el que tenga puesto su web
                  </Button>
                </div>
              )}
            </Block>
            <Block icon={<ToggleRight size={18} aria-hidden />} title="Modos junto a la caja">
              <p className="text-[15px] text-ink-2">{f.modes.length ? f.modes.map((m) => m.name + (m.on ? " (encendido)" : "")).join(" · ") : "No vi interruptores de modo."}</p>
            </Block>
            <Block icon={<Menu size={18} aria-hidden />} title="Menú «+»">
              <p className="text-[15px] text-ink-2">{f.plus.length ? f.plus.join(" · ") : "No encontré su botón «+»."}</p>
            </Block>
            <Block icon={<FileUp size={18} aria-hidden />} title="Archivos">
              <p className="text-[15px] text-ink-2">
                {f.files.length
                  ? `Acepta: ${f.files.map((x) => x.accept || "cualquier archivo").join(" · ")}${f.files.some((x) => x.multiple) ? " (varios a la vez)" : ""}.`
                  : "No vi dónde subir archivos: por aquí no se le pueden adjuntar."}
              </p>
            </Block>

            {(!f.found.model || !f.found.plus) && (
              <Block icon={<Hand size={18} aria-hidden />} title="¿Falta algo? Enséñame dónde está">
                <p className="text-[15px] text-ink-2">
                  Pulsa el botón, ve a la ventanita de webllm y haz un clic en lo que falta. Ese clic no hace nada en la web: solo me enseña dónde está.
                </p>
                <div className="flex flex-wrap gap-2">
                  {!f.found.model && (
                    <Button variant="soft" icon={busy === "model" ? <Loader2 size={18} className="animate-spin" aria-hidden /> : <ListChecks size={18} aria-hidden />}
                      disabled={!!busy} onClick={() => run("model", () => api.ensename(ai, "model"), "Aprendido. Pulsa Descubrir otra vez.")}>
                      {busy === "model" ? "Esperando tu clic…" : "El selector de modelos"}
                    </Button>
                  )}
                  {!f.found.plus && (
                    <Button variant="soft" icon={busy === "plus" ? <Loader2 size={18} className="animate-spin" aria-hidden /> : <Menu size={18} aria-hidden />}
                      disabled={!!busy} onClick={() => run("plus", () => api.ensename(ai, "plus"), "Aprendido. Pulsa Descubrir otra vez.")}>
                      {busy === "plus" ? "Esperando tu clic…" : "El botón «+»"}
                    </Button>
                  )}
                </div>
              </Block>
            )}
          </>
        )}
        {f && (
          <Block icon={<Wrench size={18} aria-hidden />} title="Si su web cambia">
            <p className="text-[15px] text-ink-2">
              {f.revision ? `Comprobada el ${readable(f.revision.when)}: ${checkWords(f.revision)}.` : "Todavía no se ha comprobado (webllm lo hace una vez al día)."}{" "}
              Si webllm no encuentra su caja o no puede leer su respuesta, intenta arreglarlo solo; si no puede, enséñaselo tú con tres clics
              en su ventanita. Tus clics no envían nada.
            </p>
            <div>
              <Button variant="soft" disabled={!!busy}
                icon={busy === "teach" ? <Loader2 size={18} className="animate-spin" aria-hidden /> : <MousePointerClick size={18} aria-hidden />}
                onClick={teachWeb}>
                {busy === "teach" && step !== null ? "Esperando tu clic…" : "Enséñame esta web (3 clics)"}
              </Button>
            </div>
            {busy === "teach" && step !== null && (
              <p className="rounded-xl bg-warn-bg px-4 py-3 text-[16px] font-semibold text-warn-ink" role="status">{TEACH_STEPS[step].text}</p>
            )}
            {f.arreglos.length > 0 && (
              <>
                <p className="mt-2 text-[15px] font-semibold">Arreglos de esta web</p>
                <ul className="flex flex-col divide-y divide-line rounded-xl border border-line" data-arreglos>
                  {f.arreglos.map((a) => (
                    <li key={a.index} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                      <span className="min-w-0 flex-1 text-[15px]">
                        <b>{a.what}</b> · {a.by === "tú" ? "me lo enseñaste tú" : `lo arregló ${a.by}`} · {readable(a.when)}
                        {a.why && a.by !== "tú" && <span className="text-muted"> ({a.why})</span>}
                      </span>
                      {a.active ? (
                        <Button size="sm" variant="ghost" icon={<Undo2 size={17} aria-hidden />} disabled={!!busy} onClick={() => undo(a.index)}>
                          Deshacer
                        </Button>
                      ) : (
                        <Badge tone="neutral" icon={<Undo2 {...ICON} />}>{a.undone ? `Deshecho el ${readable(a.undone)}` : "Deshecho"}</Badge>
                      )}
                    </li>
                  ))}
                </ul>
                {f.arreglos.filter((a) => a.active).length > 1 && (
                  <p className="text-[15px] text-muted">
                    <button type="button" className="cursor-pointer font-semibold text-accent-soft-ink underline" disabled={!!busy}
                      onClick={() => run("descubrir", () => api.fichaOlvidar(ai), "Deshecho todo: la web vuelve a como webllm la conocía.")}>
                      Deshacer todos
                    </button>
                  </p>
                )}
              </>
            )}
          </Block>
        )}
      </div>
    </Modal>
  );
}
