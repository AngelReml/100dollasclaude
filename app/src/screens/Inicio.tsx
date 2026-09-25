import { AppWindow, Cpu, LifeBuoy, Server, MessageSquarePlus, MonitorCheck, TestTube2, Unplug } from "lucide-react";
import type { ReactNode } from "react";
import type { Ai } from "../api";
import { go, useOpenGuide } from "../nav";
import { useStore } from "../state";
import { AiAvatar, KindLabel } from "../ui/Ai";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Empty } from "../ui/Empty";
import { FixButtons } from "../ui/Fix";
import { Page, SectionTitle } from "../ui/Page";
import { AiStateBadge, Badge } from "../ui/Status";
import type { FixAction } from "../fix";

const when = (ts: number) =>
  new Date(ts * 1000).toLocaleString("es-ES", { weekday: "long", hour: "2-digit", minute: "2-digit" });

function aiLine(ai: Ai): { text: string; actions: FixAction[] } {
  switch (ai.state) {
    case "lista":
      return {
        text: ai.kind === "chat" && ai.cap ? `Hoy: ${ai.today} de ${ai.cap} mensajes.` : "Lista para preguntar. No gasta mensajes de tus chats.",
        actions: [],
      };
    case "en_pausa":
      return {
        text: `En pausa hasta el ${ai.until ? when(ai.until) : "aviso"}${ai.detail ? ` · ${ai.detail}` : ""}. Cuando lo hayas arreglado, reanúdala.`,
        actions: ["reanudar"],
      };
    case "sin_sesion":
      return { text: "Entra con tu cuenta en su web y comprueba otra vez.", actions: ["abrir", "comprobar"] };
    case "sin_chrome":
      return { text: "Hace falta Chrome abierto con la extensión webllm.", actions: ["guia"] };
    case "apagada":
      return { text: "El programa que conecta las IAs por API está apagado.", actions: ["encender"] };
    case "saturada":
      return { text: "Tiene demasiada gente ahora mismo. No es cosa de tu cuenta: prueba en un rato.", actions: ai.kind === "chat" ? ["comprobar"] : [] };
  }
}

function AiCard({ ai }: { ai: Ai }) {
  const line = aiLine(ai);
  return (
    <Card className="flex flex-col gap-3 p-5">
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
    </Card>
  );
}

function PieceCard({ icon, name, ok, good, bad, children }: { icon: ReactNode; name: string; ok: boolean; good: string; bad: string; children?: ReactNode }) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-ink-2">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[17px] font-semibold leading-tight">{name}</p>
          <div className="mt-1.5">
            <Badge tone={ok ? "ok" : "bad"} icon={ok ? <MonitorCheck size={16} aria-hidden /> : <Unplug size={16} aria-hidden />}>
              {ok ? good : bad}
            </Badge>
          </div>
        </div>
      </div>
      {!ok && children}
    </Card>
  );
}

export function Inicio() {
  const { estado, offline } = useStore();
  const openGuide = useOpenGuide();
  const ready = estado ? estado.ais.filter((a) => a.state === "lista").length : 0;
  return (
    <Page
      title="Inicio"
      subtitle={estado ? `${ready} de ${estado.ais.length} IAs listas para usar.` : "Mirando cómo está todo…"}
      action={
        <Button variant="primary" size="lg" icon={<MessageSquarePlus size={20} aria-hidden />} onClick={() => go("preguntar")}>
          Hacer una pregunta
        </Button>
      }
    >
      {offline && (
        <div className="mb-6">
          <Empty icon={<Unplug size={26} />} title="webllm no responde" text="Cierra esta ventana y vuelve a abrir webllm con su icono. Si sigue igual, haz doble clic en ACTUALIZAR." />
        </div>
      )}
      {estado && (
        <>
          <section className="mb-10">
            <SectionTitle>Lo que hace falta</SectionTitle>
            <div className="grid gap-4 md:grid-cols-3">
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
            </div>
          </section>
          <section className="mb-10">
            <SectionTitle>Tus IAs</SectionTitle>
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {estado.ais.map((ai) => (
                <AiCard key={ai.name} ai={ai} />
              ))}
            </div>
          </section>
          <section className="flex flex-wrap gap-2 border-t border-line pt-6">
            <Button variant="ghost" icon={<LifeBuoy size={18} aria-hidden />} onClick={openGuide}>
              Guía de primera vez
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
