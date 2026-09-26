import { ExternalLink, Radio, Wrench } from "lucide-react";
import { api, ApiError } from "../api";
import { useStore } from "../state";
import { Button } from "./Button";
import { useToast } from "./Toast";

/**
 * "Continuar en la web" (PLAN-v5 F6, D16): that exact conversation, in a normal tab of Iván's Chrome; what he
 * writes there is recorded in the same conversation (history and memory). And, when a page had changed, who
 * repaired it (nothing was sent to find out).
 */
export function WebRow({ runId, provider, label, url, repairedBy, byIvan }: {
  runId: string | null; provider: string; label: string; url?: string; repairedBy?: string; byIvan?: boolean;
}) {
  const toast = useToast();
  const { refresh } = useStore();
  if (!repairedBy && !byIvan && !(url && runId)) return null;
  const go = async () => {
    try {
      await api.continuar(runId as string, provider);
      toast(`Abierta en tu Chrome. Lo que escribas allí a ${label} se guarda aquí.`);
      refresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No pude abrirla.", "bad");
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line px-5 py-2.5 text-[15px]">
      {byIvan && <span className="text-ink-2">Escrita por ti en la web de {label}.</span>}
      {repairedBy && (
        <span className="inline-flex items-center gap-1.5 text-ink-2">
          <Wrench size={16} aria-hidden /> Su web había cambiado: la arregló {repairedBy}, sin enviar nada.
        </span>
      )}
      {url && runId && (
        <Button size="sm" variant="ghost" icon={<ExternalLink size={17} aria-hidden />} onClick={go}>
          Continuar en la web
        </Button>
      )}
    </div>
  );
}

/** While webllm records a conversation Iván goes on with by hand, it says so, with a way to stop it. */
export function ObservingBanner() {
  const { estado, refresh } = useStore();
  const toast = useToast();
  const list = estado?.observing ?? [];
  if (!list.length) return null;
  return (
    <div className="mb-6 flex flex-col gap-2">
      {list.map((o) => (
        <div key={o.tab} className="flex flex-wrap items-center gap-3 rounded-2xl bg-surface-2 px-5 py-3 text-[16px]" role="status">
          <Radio size={20} className="shrink-0 text-bad-ink" aria-hidden />
          <span className="min-w-0 flex-1">
            Registrando tu conversación con <b>{o.label}</b> en tu Chrome (desde las {o.since}). Lo que escribas allí se guarda en tu historial.
          </span>
          <Button size="sm" variant="secondary"
            onClick={() => api.dejarDeRegistrar(o.tab).then(() => { toast("Ya no se registra."); refresh(); }, () => toast("No se pudo.", "bad"))}>
            Dejar de registrar
          </Button>
        </div>
      ))}
    </div>
  );
}
