import { BookMarked, FolderCheck, FolderX, Power } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Memoria } from "../api";
import { Button } from "./Button";
import { Card } from "./Card";
import { Badge } from "./Status";
import { useToast } from "./Toast";

const ICON = { size: 16, strokeWidth: 2.25, "aria-hidden": true } as const;

/**
 * "Memoria en Obsidian" (PLAN-v5 F5): the folder of Iván's vault (inside Google Drive). webllm writes each
 * conversation there as it happens, in its own webllm/ folder, and never reads anything back.
 */
export function MemoriaCard() {
  const toast = useToast();
  const [m, setM] = useState<Memoria | null>(null);
  const [dir, setDir] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.memoria().then((x) => { setM(x); setDir(x.dir); }, () => setM(null));
  }, []);
  const save = async (enabled: boolean) => {
    setBusy(true);
    try {
      const x = await api.guardarMemoria(dir, enabled);
      setM(x);
      toast(enabled ? "Listo: cada conversación se guardará en tu vault, en la carpeta webllm." : "Memoria apagada: no se escribe nada más.");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo guardar.", "bad");
    } finally {
      setBusy(false);
    }
  };
  if (!m) return null;
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
      <p className="text-[15px] text-ink-2">
        {m.enabled
          ? `Cada conversación se guarda en ${m.dir}\\webllm mientras ocurre (${m.conversations} ${m.conversations === 1 ? "conversación" : "conversaciones"}${m.last ? `; la última, el ${m.last}` : ""}). webllm nunca lee nada de ahí.`
          : "Escribe la carpeta de tu vault de Obsidian (dentro de Google Drive). webllm guardará ahí cada conversación, en su propia carpeta «webllm», y nunca leerá nada de ahí."}
      </p>
      {m.enabled && m.error && <p className="text-[15px] text-bad-ink">Último fallo: {m.error}. Comprueba que Google Drive está abierto y la carpeta sigue ahí.</p>}
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
      <div className="flex flex-wrap gap-2">
        <Button variant="soft" disabled={busy || !dir.trim()} onClick={() => save(true)}>
          {m.enabled ? "Guardar la carpeta" : "Encender la memoria"}
        </Button>
        {m.enabled && (
          <Button variant="ghost" disabled={busy} onClick={() => save(false)}>
            Apagar
          </Button>
        )}
      </div>
    </Card>
  );
}
