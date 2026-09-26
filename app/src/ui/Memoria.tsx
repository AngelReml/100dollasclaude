import { BookMarked, FolderCheck, FolderX, History, Power, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Memoria } from "../api";
import { Button } from "./Button";
import { Card } from "./Card";
import { Modal } from "./Modal";
import { Badge } from "./Status";
import { useToast } from "./Toast";

const ICON = { size: 16, strokeWidth: 2.25, "aria-hidden": true } as const;

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * "Memoria en Obsidian" (PLAN-v5 F5): the folder of Iván's vault, wherever it is. webllm writes there, as it
 * happens, each conversation and, separately, each answer of each AI with its date as title (his decision,
 * 26-sep-2026), in its own webllm/ folder, and never reads anything back.
 */
export function MemoriaCard() {
  const toast = useToast();
  const [m, setM] = useState<Memoria | null>(null);
  const [dir, setDir] = useState("");
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  useEffect(() => {
    api.memoria().then(
      (x) => {
        setM(x);
        setDir(x.dir);
      },
      () => setM(null),
    );
    // the counts and "Guardando / No puede escribir" follow what happens (the folder field is left alone)
    const every = window.setInterval(() => api.memoria().then(setM, () => undefined), 5000);
    return () => window.clearInterval(every);
  }, []);
  const save = async (enabled: boolean) => {
    setBusy(true);
    try {
      const x = await api.guardarMemoria(dir, enabled);
      setM(x);
      setDir(x.dir);
      toast(enabled ? "Listo: desde ahora se guarda todo en tu vault, en la carpeta webllm." : "Memoria apagada: no se escribe nada más.");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo guardar.", "bad");
    } finally {
      setBusy(false);
    }
  };
  const earlier = async () => {
    setBusy(true);
    try {
      setM(await api.memoriaAnteriores());
      toast("Copiando lo de antes: en unos segundos está en tu vault.");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo copiar.", "bad");
    } finally {
      setBusy(false);
    }
  };
  const rewrite = async () => {
    setAsking(false);
    setBusy(true);
    try {
      setM(await api.reescribirMemoria());
      toast("Reescribiendo todo desde el registro de webllm.");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo reescribir.", "bad");
    } finally {
      setBusy(false);
    }
  };
  if (!m) return null;
  const where = `${m.dir.replace(/[\\/]+$/, "")}\\webllm`;
  return (
    <Card className="flex flex-col gap-3 p-5" data-card="memoria">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-ink-2">
          <BookMarked size={22} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[17px] font-semibold leading-tight">Memoria en Obsidian</p>
          <div className="mt-1.5">
            {m.enabled && !m.error ? (
              <Badge tone="ok" icon={<FolderCheck {...ICON} />}>Guardando</Badge>
            ) : m.enabled ? (
              <Badge tone="bad" icon={<FolderX {...ICON} />}>No puede escribir</Badge>
            ) : (
              <Badge tone="neutral" icon={<Power {...ICON} />}>Apagada</Badge>
            )}
          </div>
        </div>
      </div>
      {m.enabled ? (
        <p className="text-[15px] text-ink-2">
          Cada conversación y, aparte, cada respuesta de cada IA (con su fecha como título) se guardan en{" "}
          <span className="break-all font-medium text-ink">{where}</span> mientras ocurren:{" "}
          {plural(m.conversations, "conversación", "conversaciones")} y {plural(m.answers, "respuesta", "respuestas")}
          {m.last ? `; lo último, el ${m.last}` : ""}. webllm nunca lee nada de ahí.
        </p>
      ) : (
        <p className="text-[15px] text-ink-2">
          Escribe la carpeta de tu vault de Obsidian, esté donde esté (en tu PC o en Google Drive). webllm guardará ahí cada
          conversación y, aparte, cada respuesta de cada IA con su fecha como título, en su propia carpeta «webllm». Nunca leerá
          nada de ahí.
        </p>
      )}
      {m.enabled && m.error && (
        <p className="text-[15px] text-bad-ink">
          No pudo guardar: {m.error}. Cuando la carpeta vuelva a estar, escribe solo lo que faltaba.
        </p>
      )}
      <label className="flex flex-col gap-1.5">
        <span className="text-[15px] font-semibold">Carpeta del vault</span>
        <input
          className="min-h-11 rounded-xl border border-line-strong bg-surface px-3 text-[16px] text-ink"
          placeholder="G:\Mi unidad\Obsidian"
          value={dir}
          onChange={(e) => setDir(e.target.value)}
          spellCheck={false}
        />
      </label>
      <div className="flex flex-col items-start gap-2">
        <Button variant="soft" disabled={busy || !dir.trim() || (m.enabled && dir.trim() === m.dir)} onClick={() => save(true)}>
          {m.enabled ? "Cambiar de carpeta" : "Encender la memoria"}
        </Button>
        {m.enabled && (
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" icon={<History size={17} aria-hidden />} disabled={busy} onClick={earlier}>
              Copiar también lo de antes
            </Button>
            <Button variant="ghost" icon={<RefreshCw size={17} aria-hidden />} disabled={busy} onClick={() => setAsking(true)}>
              Reescribir todo
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => save(false)}>
              Apagar
            </Button>
          </div>
        )}
      </div>
      <Modal
        open={asking}
        onOpenChange={setAsking}
        title="¿Reescribir todo?"
        description="webllm vuelve a escribir, desde su registro, todas las conversaciones y respuestas de la carpeta webllm."
      >
        <p className="mb-5 text-[16px] text-ink-2">
          Si cambiaste a mano algún archivo de la carpeta webllm, ese cambio se pierde. Tus otras notas no se tocan. Sirve si
          borraste algo de ahí o lo quieres como el primer día.
        </p>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => setAsking(false)}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={rewrite}>
            Sí, reescribir todo
          </Button>
        </div>
      </Modal>
    </Card>
  );
}
