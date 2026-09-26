import { AppWindow, Cpu, LifeBuoy, Plug, Plus, Power, ScanSearch, Server, MessageSquarePlus, MonitorCheck, OctagonX, TestTube2, Unplug } from "lucide-react";
import { useState, type ReactNode } from "react";
import { api, ApiError, type Ai } from "../api";
import { go, useOpenAddAi, useOpenGuide } from "../nav";
import { useStore } from "../state";
import { AiAvatar, KindLabel } from "../ui/Ai";
import { ComiteCard } from "../ui/Comite";
import { MemoriaCard } from "../ui/Memoria";
import { ObservingBanner } from "../ui/Observando";
import { RemoveAiButton } from "../ui/AddAi";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Empty } from "../ui/Empty";
import { FichaDialog } from "../ui/Ficha";
import { FixButtons } from "../ui/Fix";
import { Page, SectionTitle } from "../ui/Page";
import { AiStateBadge, Badge } from "../ui/Status";
import { useToast } from "../ui/Toast";
import type { FixAction } from "../fix";

const when = (ts: number) =>
  new Date(ts * 1000).toLocaleString("es-ES", { weekday: "long", hour: "2-digit", minute: "2-digit" });

function aiLine(ai: Ai): { text: string; actions: FixAction[] } {
  switch (ai.state) {
    case "lista":
      return {
        text:
          ai.kind === "chat" && ai.cap
            ? `Hoy: ${ai.today} de ${ai.cap} mensajes.`
            : ai.kind === "local"
              ? "Lista. Funciona en tu PC: no gasta ninguna cuenta."
              : "Lista para preguntar. No gasta mensajes de tus chats.",
        actions: [],
      };
    case "en_pausa":
      return {
        text: `En pausa hasta el ${ai.until ? when(ai.until) : "aviso"}${ai.detail ? ` · ${ai.detail}` : ""}. Cuando lo hayas arreglado, reanúdala.`,
        actions: ["reanudar"],
      };
    case "sin_sesion":
      return { text: "Pulsa Conectar y entra con tu cuenta en la ventana que se abre.", actions: ["conectar"] };
    case "sin_chrome":
      return { text: "Hace falta Chrome abierto con la extensión webllm.", actions: ["guia"] };
    case "apagada":
      return ai.kind === "local"
        ? { text: `${ai.server_name ?? "El programa"} está apagado.`, actions: ["encender_local"] }
        : { text: "El programa que conecta las IAs por API está apagado.", actions: ["encender"] };
    case "saturada":
      return { text: "Tiene demasiada gente ahora mismo. No es cosa de tu cuenta: prueba en un rato.", actions: [] };
  }
}

export function AiCard({ ai }: { ai: Ai }) {
  const line = aiLine(ai);
  const [ficha, setFicha] = useState(false);
  return (
    <Card className="flex flex-col gap-3 p-5" data-card={ai.name}>
      <div className="flex items-center gap-3">
        <AiAvatar name={ai.name} label={ai.label} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[18px] font-semibold leading-tight">{ai.label}</p>
          <KindLabel kind={ai.kind} />
        </div>
      </div>
      <div>
        <AiStateBadge state={ai.state} />
      </div>
      <p className="text-[15px] text-ink-2">{line.text}</p>
      {line.actions.length > 0 && <FixButtons actions={line.actions} ai={ai.name} />}
      {ai.kind === "chat" && (
        <div>
          <Button size="sm" variant="soft" icon={<ScanSearch size={18} aria-hidden />} onClick={() => setFicha(true)}>
            Ficha: modelos y modos
          </Button>
          <FichaDialog ai={ai.name} label={ai.label} open={ficha} onOpenChange={setFicha} />
        </div>
      )}
      {ai.custom && (
        <div className="-mb-1 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
          <span className="min-w-0 truncate text-[15px] text-muted">{ai.catalog ? "De la lista de webllm" : "Añadida por ti"} · {ai.url?.replace(/^https:\/\//, "").replace(/\/$/, "")}</span>
          <RemoveAiButton name={ai.name} label={ai.label} />
        </div>
      )}
    </Card>
  );
}

const GROUPS: { kind: Ai["kind"]; title: string }[] = [
  { kind: "chat", title: "Chats en tu Chrome" },
  { kind: "api", title: "IAs por API" },
  { kind: "local", title: "En tu PC" },
];

function StartLocal({ server, name }: { server: string; name: string }) {
  const { refresh } = useStore();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <div>
      <Button
        variant="soft"
        icon={<Power size={18} aria-hidden />}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const r = await api.encenderLocal(server);
            toast(r.already ? `${name} ya estaba encendido.` : `Encendiendo ${name}… tarda unos segundos.`);
            await refresh();
          } catch (err) {
            toast(err instanceof ApiError ? err.message : "No se pudo encender.", "bad");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Un momento…" : `Encender ${name}`}
      </Button>
    </div>
  );
}

function PieceCard({
  icon,
  name,
  ok,
  good,
  bad,
  optional = false,
  children,
}: {
  icon: ReactNode;
  name: string;
  ok: boolean;
  good: string;
  bad: string;
  /** Off but nothing depends on it yet: grey, not red. */
  optional?: boolean;
  children?: ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-ink-2">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[17px] font-semibold leading-tight">{name}</p>
          <div className="mt-1.5">
            <Badge tone={ok ? "ok" : optional ? "neutral" : "bad"} icon={ok ? <MonitorCheck size={16} aria-hidden /> : <Unplug size={16} aria-hidden />}>
              {ok ? good : bad}
            </Badge>
          </div>
        </div>
      </div>
      {!ok && children}
    </Card>
  );
}

/** "Parar todo": stops every question in progress and its job in Chrome, and says what it stopped. */
function StopAll() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const stop = async () => {
    setBusy(true);
    try {
      const r = await api.pararTodo();
      const what = [
        r.parados ? (r.parados === 1 ? "1 pregunta" : `${r.parados} preguntas`) : "",
        r.chats.length ? (r.chats.length === 1 ? "1 chat de la ventanita" : `${r.chats.length} chats de la ventanita`) : "",
      ].filter(Boolean);
      toast(what.length ? `Parado: ${what.join(" y ")}.` : "No había nada en marcha.");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "No se pudo parar.", "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="secondary" size="lg" icon={<OctagonX size={20} aria-hidden />} onClick={stop} disabled={busy}>
      {busy ? "Parando…" : "Parar todo"}
    </Button>
  );
}

export function Inicio() {
  const { estado, offline } = useStore();
  const openGuide = useOpenGuide();
  const openAdd = useOpenAddAi();
  const ready = estado ? estado.ais.filter((a) => a.state === "lista").length : 0;
  return (
    <Page
      title="Inicio"
      subtitle={estado ? `${ready} de ${estado.ais.length} IAs listas para usar.` : "Mirando cómo está todo…"}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <StopAll />
          <Button variant="primary" size="lg" icon={<MessageSquarePlus size={20} aria-hidden />} onClick={() => go("preguntar")}>
            Hacer una pregunta
          </Button>
        </div>
      }
    >
      <ObservingBanner />
      {offline && (
        <div className="mb-6">
          <Empty icon={<Unplug size={26} />} title="webllm no responde" text="Cierra esta ventana y vuelve a abrir webllm con su icono. Si sigue igual, haz doble clic en ACTUALIZAR." />
        </div>
      )}
      {estado && (
        <>
          <section className="mb-10">
            <SectionTitle>Lo que hace falta</SectionTitle>
            <div className="grid items-start gap-4 md:grid-cols-3">
              <PieceCard icon={<Cpu size={22} aria-hidden />} name="webllm" ok good="Funcionando" bad="Parado" />
              <PieceCard icon={<AppWindow size={22} aria-hidden />} name="Chrome con la extensión" ok={estado.chrome} good="Conectado" bad="No conectado">
                <p className="text-[15px] text-ink-2">Sin esto no se puede preguntar a los chats (las IAs por API sí funcionan).</p>
                <div>
                  <Button variant="soft" icon={<LifeBuoy size={18} aria-hidden />} onClick={openGuide}>
                    Cómo arreglarlo
                  </Button>
                </div>
              </PieceCard>
              <PieceCard icon={<Server size={22} aria-hidden />} name="IAs por API (OmniRoute)" ok={estado.omniroute} good="Encendido" bad="Apagado">
                <p className="text-[15px] text-ink-2">Sin esto no responden z.ai, groq ni Nemotron.</p>
                <FixButtons actions={["encender"]} ai={estado.ais.find((a) => a.kind === "api")?.name ?? ""} />
              </PieceCard>
              {estado.local_servers.map((srv) => (
                <PieceCard key={srv.key} icon={<Cpu size={22} aria-hidden />} name={`${srv.name} (IAs en tu PC)`} ok={srv.up} good="Encendido" bad="Apagado" optional={!srv.models}>
                  <p className="text-[15px] text-ink-2">
                    {srv.models ? `Sin esto no responden sus ${srv.models} modelo${srv.models > 1 ? "s" : ""}.` : "Enciéndelo para ver sus modelos aquí."}
                  </p>
                  {srv.installed && <StartLocal server={srv.key} name={srv.name} />}
                </PieceCard>
              ))}
              <MemoriaCard />
            </div>
          </section>
          <section className="mb-10">
            <SectionTitle>Evaluar una idea</SectionTitle>
            <ComiteCard />
          </section>
          <section className="mb-10">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <SectionTitle className="">Tus IAs</SectionTitle>
              <div className="flex flex-wrap gap-2">
                <Button variant="soft" icon={<Plug size={19} aria-hidden />} onClick={() => go("conectores")}>
                  Conectar más chats
                </Button>
                <Button variant="soft" icon={<Plus size={19} aria-hidden />} onClick={openAdd}>
                  Añadir otra IA
                </Button>
              </div>
            </div>
            {GROUPS.map((g) => {
              const members = estado.ais.filter((a) => a.kind === g.kind);
              if (!members.length) return null;
              return (
                <div key={g.kind} className="mb-6">
                  <h3 className="mb-2.5 text-[16px] font-semibold text-ink-2">{g.title}</h3>
                  <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                    {members.map((ai) => (
                      <AiCard key={ai.name} ai={ai} />
                    ))}
                  </div>
                </div>
              );
            })}
          </section>
          <section className="flex flex-wrap gap-2 border-t border-line pt-6">
            <Button variant="ghost" icon={<LifeBuoy size={18} aria-hidden />} onClick={openGuide}>
              Ver la guía otra vez
            </Button>
            <a href="/" target="_blank" rel="noopener" className="inline-flex min-h-11 items-center gap-2 rounded-xl px-4 text-[15px] font-semibold text-ink-2 hover:bg-surface-2 hover:text-ink">
              <TestTube2 size={18} aria-hidden />
              Pruebas a fondo
            </a>
          </section>
        </>
      )}
    </Page>
  );
}
