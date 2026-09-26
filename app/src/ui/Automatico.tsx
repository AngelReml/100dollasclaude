import { Check, KeyRound, ListChecks, Route, Search, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type ApiCard, type Automatico, type AutoTest, type AutoTry, type Privacidad } from "../api";
import { Button } from "./Button";
import { Card } from "./Card";
import { Modal } from "./Modal";
import { useToast } from "./Toast";

/**
 * "Automático" (PLAN-v5 D7, F8): in Open WebUI, "webllm · Automático" chooses the AI for each question with rules
 * written in a file. Here Iván sees those rules, what each kind of question would get right now (and why the ones
 * before are skipped), tries his own questions without sending anything, and looks after the AIs by API.
 */
export function AutomaticoCard() {
  const toast = useToast();
  const [a, setA] = useState<Automatico | null>(null);
  const [testing, setTesting] = useState(false);
  const [apis, setApis] = useState(false);
  useEffect(() => {
    api.automatico().then(setA, () => setA(null));
  }, []);
  if (!a) return null;
  const marked = a.pruebas.filter((p) => p.bien !== null);
  const good = marked.filter((p) => p.bien).length;
  return (
    <Card className="flex flex-col gap-5 p-6" data-card="automatico">
      <div className="min-w-0">
        <h3 className="flex items-center gap-2 text-[18px] font-semibold">
          <Route size={20} aria-hidden /> Automático
        </h3>
        <p className="mt-1 max-w-[80ch] text-[15px] text-ink-2">
          En Open WebUI elige <b>webllm · Automático</b> y pregunta: elige la IA según lo que preguntes, con estas reglas, y la
          primera línea de la respuesta dice cuál eligió y por qué. Si la que elige falla, te lo dice y no pregunta a otra
          sin ti. No es el de partida: siempre puedes elegir tú.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div>
          <p className="mb-2 text-[15px] font-semibold">Las reglas, en este orden</p>
          <ol className="flex list-decimal flex-col gap-1.5 pl-6 text-[15px] text-ink-2">
            {a.reglas.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ol>
        </div>
        <div>
          <p className="mb-2 text-[15px] font-semibold">Si preguntas ahora</p>
          <ul className="flex flex-col gap-3">
            {a.tipos.map((t) => (
              <li key={t.key} className="rounded-xl bg-surface-2 p-3">
                <p className="text-[15px]">
                  <b>{t.name}</b> → {t.now ? <b>{t.now}</b> : <span className="text-bad-ink">nadie disponible</span>}
                </p>
                <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label={`La lista de ${t.name}`}>
                  {t.rows.map((r) => (
                    <li key={r.key} title={r.why || undefined}
                      className={`rounded-lg px-2 py-0.5 text-[15px] ${r.state === "no" ? "text-ink-2" : "bg-ok-bg text-ok-ink"}`}>
                      {r.state !== "no" && <Check size={14} className="mr-1 inline" aria-hidden />}
                      {r.label}
                      {r.state === "no" && <span className="text-muted"> · {r.why}</span>}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="soft" icon={<ListChecks size={18} aria-hidden />} onClick={() => setTesting(true)}>
          Probar con tus preguntas
        </Button>
        <Button variant="soft" icon={<KeyRound size={18} aria-hidden />} onClick={() => setApis(true)}>
          Las IAs por API
        </Button>
        {marked.length > 0 && (
          <span className="text-[15px] text-ink-2">
            Tu prueba: <b>{good} de {marked.length}</b> bien elegidas{marked.length >= 10 ? (good >= 9 ? " (la meta era 9 de 10)." : " (la meta es 9 de 10).") : "."}
          </span>
        )}
      </div>
      <p className="text-[15px] text-muted">{a.fuente}. Revisada el {a.checked}.</p>
      {testing && <TestDialog saved={a.pruebas} onClose={() => setTesting(false)} onSaved={(p) => setA({ ...a, pruebas: p })} />}
      {apis && (
        <ApisDialog fichas={a.fichas} onClose={() => setApis(false)}
          onChange={(next) => { setA(next); toast("Hecho."); }} />
      )}
    </Card>
  );
}

/** Two questions of each kind, to be replaced by Iván's own (PLAN-v5 F8: "10 preguntas de prueba, 2 de cada tipo"). */
const SUGGESTED = [
  "Hazme un script en Python que cambie el nombre de las fotos de una carpeta por su fecha",
  "Me sale este error: TypeError: undefined is not a function. ¿Qué hago?",
  "¿Cuántos habitantes tiene Valencia?",
  "Tradúceme al inglés: nos vemos mañana a las diez",
  "Resume este documento en cinco puntos",
  "¿Qué dice este contrato sobre cancelar el servicio?",
  "Busca las últimas noticias sobre la ley europea de IA, con fuentes",
  "¿Qué se sabe de los efectos del café en el sueño? Dame referencias",
  "¿Merece la pena montar una tienda online de cerámica hecha a mano?",
  "Evalúa mi idea: una app para compartir coche entre vecinos",
];

function TestDialog({ saved, onClose, onSaved }: { saved: AutoTest[]; onClose: () => void; onSaved: (p: AutoTest[]) => void }) {
  const toast = useToast();
  const [questions, setQuestions] = useState<string[]>(saved.length ? saved.map((s) => s.texto) : SUGGESTED);
  const [results, setResults] = useState<AutoTry[] | null>(null);
  const [marks, setMarks] = useState<Record<number, boolean | null>>(
    Object.fromEntries(saved.map((s, i) => [i, s.bien])),
  );
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const res = await api.probarAutomatico(questions.filter((q) => q.trim()));
      setResults(res.resultados);
      setMarks({});
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo probar.", "bad");
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    if (!results) return;
    try {
      const res = await api.guardarPruebas(results.map((r, i) => ({ texto: r.texto, tipo: r.tipo, elegida: r.elegida, bien: marks[i] ?? null })));
      onSaved(res.preguntas);
      toast("Prueba guardada.");
      onClose();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo guardar.", "bad");
    }
  };
  return (
    <Modal open wide onOpenChange={(o) => !o && onClose()} title="Probar Automático"
      description="Cambia estas preguntas por las tuyas de verdad, dos de cada tipo. Se mira qué IA elegiría Automático; no se envía nada a ninguna IA.">
      {!results ? (
        <div className="flex flex-col gap-2.5">
          {questions.map((q, i) => (
            <input key={i} aria-label={`Pregunta de prueba ${i + 1}`} value={q} maxLength={2000}
              onChange={(e) => setQuestions(questions.map((x, j) => (j === i ? e.target.value : x)))}
              className="min-h-11 rounded-xl border border-line-strong bg-surface px-3 text-[16px]" />
          ))}
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancelar</Button>
            <Button variant="primary" icon={<Search size={18} aria-hidden />} onClick={run} disabled={busy}>
              {busy ? "Mirando…" : "Ver qué elegiría"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-[15px] text-ink-2">Marca cada una: ¿es la IA que tú habrías elegido para esa pregunta?</p>
          <ol className="flex flex-col gap-2.5">
            {results.map((r, i) => (
              <li key={i} className="rounded-xl bg-surface-2 p-3">
                <p className="text-[16px]">{r.texto}</p>
                <p className="mt-1 text-[15px] text-ink-2">
                  {r.tipo} → <b className="text-ink">{r.elegida}</b> ({r.por_que})
                  {r.saltadas.length > 0 && <span className="text-muted">. Antes: {r.saltadas.map(([w, why]) => `${w}, ${why}`).join("; ")}</span>}
                </p>
                <div className="mt-2 flex gap-2" role="radiogroup" aria-label={`¿Bien elegida la ${i + 1}?`}>
                  {([true, false] as const).map((v) => (
                    <button key={String(v)} type="button" role="radio" aria-checked={marks[i] === v}
                      onClick={() => setMarks({ ...marks, [i]: v })}
                      className={`inline-flex min-h-10 items-center gap-1.5 rounded-lg border px-3 text-[15px] font-semibold ${marks[i] === v ? (v ? "border-transparent bg-ok-bg text-ok-ink" : "border-transparent bg-bad-bg text-bad-ink") : "border-line-strong text-ink-2"}`}>
                      {v ? <Check size={16} aria-hidden /> : <X size={16} aria-hidden />} {v ? "Bien" : "Mal"}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[15px] text-ink-2">
              {Object.values(marks).filter((m) => m === true).length} de {results.length} bien
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setResults(null)}>Cambiar las preguntas</Button>
              <Button variant="primary" onClick={save}>Guardar la prueba</Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

const PRIVACY_TEXT: Record<Privacidad, string> = {
  no_entrena: "No usa lo que escribes para entrenar",
  sin_comprobar: "Sin comprobar",
  entrena_salvo_que_lo_apagues: "Entrena con lo que escribes si no lo apagas",
  puede_entrenar: "Puede usar lo que escribes para entrenar",
};

function ApisDialog({ fichas, onClose, onChange }: { fichas: ApiCard[]; onClose: () => void; onChange: (a: Automatico) => void }) {
  const toast = useToast();
  const [found, setFound] = useState<Record<string, string[]> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (key: string, work: () => Promise<Automatico>) => {
    setBusy(key);
    try {
      onChange(await work());
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo.", "bad");
    } finally {
      setBusy(null);
    }
  };
  const look = async () => {
    setBusy("buscar");
    try {
      setFound((await api.omnirouteModelos()).modelos);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo leer OmniRoute.", "bad");
    } finally {
      setBusy(null);
    }
  };
  return (
    <Modal open wide onOpenChange={(o) => !o && onClose()} title="Las IAs por API"
      description="La ficha de cada una. Para encender una nueva, crea su clave en la web del proveedor, ponla en OmniRoute y búscala aquí.">
      <div className="mb-4">
        <Button variant="soft" icon={<Search size={18} aria-hidden />} onClick={look} disabled={busy === "buscar"}>
          {busy === "buscar" ? "Mirando OmniRoute…" : "Buscar en OmniRoute"}
        </Button>
      </div>
      <ul className="flex flex-col gap-3">
        {fichas.map((f) => {
          const allowed = f.privada === true;
          const candidates = found?.[f.key] ?? [];
          return (
            <li key={f.key} className="rounded-xl border border-line p-4" data-ficha={f.key}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-[16px] font-semibold">{f.name}</p>
                <p className={`text-[15px] ${f.configurada ? "text-ok-ink" : "text-ink-2"}`}>
                  {f.configurada ? `Encendida${f.model ? ` (${f.model})` : ""}` : "Sin configurar"}
                </p>
              </div>
              <p className="mt-1 text-[15px] text-ink-2">
                {f.proveedor} · {f.hace}. Gratis: {f.limites}. Ve imágenes: {f.imagenes === "si" ? "sí" : f.imagenes === "no" ? "no" : "no se sabe"}.
              </p>
              <div className={`mt-2 rounded-lg p-2.5 text-[15px] ${allowed ? "bg-surface-2" : "bg-warn-bg text-warn-ink"}`}>
                <p className="flex items-start gap-1.5">
                  {allowed ? <ShieldCheck size={17} className="mt-0.5 shrink-0" aria-hidden /> : <ShieldAlert size={17} className="mt-0.5 shrink-0" aria-hidden />}
                  <span>
                    <b>{PRIVACY_TEXT[f.privacidad.estado]}.</b> {f.privacidad.detalle}{" "}
                    {allowed ? "Automático y el Comité la usan solos." : "Automático y el Comité no la usan solos: solo si la eliges tú."}
                    {f.decidido_por_ti && " (Lo decidiste tú.)"}
                  </span>
                </p>
                {!allowed && f.privacidad.como_evitarlo && <p className="mt-1">{f.privacidad.como_evitarlo}</p>}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {!allowed && (
                  <Button variant="soft" disabled={busy === f.key} onClick={() => act(f.key, () => api.privacidadApi(f.key, true))}>
                    {f.privacidad.estado === "entrena_salvo_que_lo_apagues" ? "Ya lo apagué" : "Permitir"}
                  </Button>
                )}
                {allowed && !f.decidido_por_ti && (
                  <Button variant="ghost" disabled={busy === f.key} onClick={() => act(f.key, () => api.privacidadApi(f.key, false))}>
                    No dejar que la usen solos
                  </Button>
                )}
                {f.decidido_por_ti && (
                  <Button variant="ghost" disabled={busy === f.key} onClick={() => act(f.key, () => api.privacidadApi(f.key, null))}>
                    Volver a lo que dice su ficha
                  </Button>
                )}
                {f.desde_omniroute && (
                  <Button variant="ghost" disabled={busy === f.key} onClick={() => act(f.key, () => api.quitarApi(f.key))}>
                    Apagar
                  </Button>
                )}
                {!f.configurada && found && !candidates.length && (
                  <span className="self-center text-[15px] text-muted">OmniRoute no la tiene todavía.</span>
                )}
              </div>
              {!f.configurada && candidates.length > 0 && (
                <ul className="mt-3 flex flex-col gap-2">
                  {candidates.map((m) => (
                    <li key={m} className="flex flex-wrap items-center gap-3">
                      <Button variant="primary" aria-label={`Encender ${m}`} disabled={busy === f.key}
                        onClick={() => act(f.key, () => api.usarApi(f.key, m))}>
                        {busy === f.key ? "Probando…" : "Encender"}
                      </Button>
                      <span className="text-[15px] text-ink-2">En OmniRoute se llama «{m}». Se prueba con un mensaje corto.</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-[15px] text-muted">Fuente: {f.fuente}.</p>
            </li>
          );
        })}
      </ul>
    </Modal>
  );
}
