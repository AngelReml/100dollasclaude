import { CircleAlert, CircleCheck, Loader2, RefreshCw, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Reparar, type Revision } from "../api";
import { Button } from "./Button";
import { Card } from "./Card";
import { checkWords, readable } from "./Ficha";
import { Badge } from "./Status";
import { useToast } from "./Toast";

const ICON = { size: 16, strokeWidth: 2.25, "aria-hidden": true } as const;

/**
 * "Webs que cambian" (PLAN-v5 F6, D17): the daily check (each chat opened and looked at, nothing sent) and the
 * switch for repairs by an AI, with which AI looks at the pages' structure. Everything else is in each chat's Ficha.
 */
export function RepararCard() {
  const toast = useToast();
  const [rev, setRev] = useState<Revision | null>(null);
  const [rep, setRep] = useState<Reparar | null>(null);
  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([api.revision(), api.reparar()]);
      setRev(a);
      setRep(b);
    } catch {
      /* the page shows nothing rather than a broken card */
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!rev?.running) return;
    const t = window.setTimeout(async () => setRev(await api.revision().catch(() => rev)), 2000);
    return () => window.clearTimeout(t);
  }, [rev]);
  const checkNow = async () => {
    try {
      setRev(await api.revisar());
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo comprobar.", "bad");
    }
  };
  const save = async (enabled: boolean, ai: string | null) => {
    try {
      setRep(await api.guardarReparar(enabled, ai));
      toast(enabled ? "Reparación con IA encendida." : "Reparación con IA apagada: si una web cambia, te lo digo y me lo enseñas tú.");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo guardar.", "bad");
    }
  };
  if (!rev || !rep) return null;
  const problems = rev.sites.filter((s) => s.state !== "bien");
  return (
    <Card className="mb-10 grid gap-6 p-6 lg:grid-cols-2" data-card="reparar">
      <section className="flex flex-col gap-3">
        <h2 className="flex items-center gap-2 text-[18px] font-semibold">
          <RefreshCw size={20} aria-hidden /> Comprobación diaria
        </h2>
        <p className="text-[15px] text-ink-2">
          Una vez al día, cuando no estás preguntando nada, webllm abre cada chat conectado y mira que siga todo en su sitio. No envía nada.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {rev.running ? (
            <Badge tone="busy" icon={<Loader2 size={16} className="animate-spin" aria-hidden />}>Comprobando…</Badge>
          ) : rev.when ? (
            <Badge tone={rev.ok === rev.total ? "ok" : "warn"} icon={rev.ok === rev.total ? <CircleCheck {...ICON} /> : <CircleAlert {...ICON} />}>
              {rev.ok} de {rev.total} bien
            </Badge>
          ) : (
            <Badge tone="neutral" icon={<RefreshCw {...ICON} />}>Aún no se ha hecho</Badge>
          )}
          <span className="text-[15px] text-muted">{rev.when ? `Última: ${readable(rev.when)}.` : ""}</span>
        </div>
        {problems.length > 0 && !rev.running && (
          <ul className="flex flex-col gap-1 text-[15px]">
            {problems.map((s) => (
              <li key={s.site}>
                <b>{s.label}</b>: {checkWords(s)}.
              </li>
            ))}
          </ul>
        )}
        <div>
          <Button variant="soft" icon={<RefreshCw size={18} aria-hidden />} disabled={rev.running} onClick={checkNow}>
            Comprobar ahora
          </Button>
        </div>
      </section>
      <section className="flex flex-col gap-3">
        <h2 className="flex items-center gap-2 text-[18px] font-semibold">
          <Wrench size={20} aria-hidden /> Reparar solas con IA
        </h2>
        <p className="text-[15px] text-ink-2">
          Si una web cambia y webllm no encuentra su caja o no puede leer su respuesta, una IA por API mira cómo está hecha la página
          (sin tus mensajes ni las respuestas) y señala dónde está. webllm lo prueba sin enviar nada y lo guarda; lo puedes deshacer en la
          Ficha de ese chat.
        </p>
        <label className="flex cursor-pointer items-center gap-3 text-[16px] font-semibold">
          <input type="checkbox" role="switch" className="h-5 w-5 accent-[var(--accent)]" checked={rep.enabled}
            onChange={(e) => save(e.target.checked, rep.ai)} />
          {rep.enabled ? "Encendida" : "Apagada: me lo enseñas tú"}
        </label>
        {rep.options.length > 0 ? (
          <label className="flex flex-wrap items-center gap-2 text-[15px]">
            <span>La IA que ayuda:</span>
            <select className="min-h-10 rounded-xl border border-line-strong bg-surface px-3 text-[16px] text-ink" value={rep.ai ?? ""}
              disabled={!rep.enabled} onChange={(e) => save(rep.enabled, e.target.value)}>
              {rep.options.map((o) => (
                <option key={o.name} value={o.name}>{o.label}</option>
              ))}
            </select>
          </label>
        ) : (
          <p className="text-[15px] text-bad-ink">No hay ninguna IA por API encendida que pueda ayudar: enciende OmniRoute.</p>
        )}
      </section>
    </Card>
  );
}
