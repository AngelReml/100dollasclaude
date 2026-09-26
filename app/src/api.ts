// Talks to the webllm server that serves this page (127.0.0.1:20130).
// The server puts its token in <meta name="webllm-token"> when it sends the page.

const TOKEN = document.querySelector<HTMLMetaElement>('meta[name="webllm-token"]')?.content ?? "";

export type Session = "lista" | "sin_sesion" | "verificacion" | "sin_chrome" | "desconocido";

export type AiState = "lista" | "en_pausa" | "sin_chrome" | "apagada" | "sin_sesion" | "saturada";

export interface Ai {
  name: string;
  label: string;
  kind: "chat" | "api" | "local";
  state: AiState;
  detail: string;
  until: number | null;
  url: string | null;
  today: number;
  cap: number | null;
  /** Local AIs only: the program on this PC that runs it. */
  server: string | null;
  server_name: string | null;
  /** Added by Iván with "+ Añadir otra IA" or connected from webllm's list (can be removed). */
  custom: boolean;
  /** Connected from webllm's list of chats (Conectores). */
  catalog: boolean;
  /** The site's own icon is available at iconUrl(name). */
  icon: boolean;
  /** Its chat is waiting for Iván right now (a verification, a pop-up, or the webllm window is
   *  covered/minimized so the page cannot write); the question goes on after. */
  waiting: "challenge" | "popup" | "hidden" | "repair" | null;
}

export interface AddStep {
  step: string;
  ok: boolean | null;
  text: string;
}

export interface AddState {
  add_id: string;
  key: string;
  name: string;
  url: string;
  status: "running" | "ok" | "failed";
  steps: AddStep[];
  error: string;
  message: string;
  detail: string;
}

/** A web chat of webllm's catalog (PLAN-v5 F3) and what Iván did with it. */
export type CatalogState = "sin_conectar" | "conectada" | "no_funciona" | "no_la_quiero";

export interface CatalogAi {
  key: string;
  name: string;
  by: string;
  url: string;
  /** tuyas = already used; 1 = plain chat, works from Spain; 2 = "puede fallar" (may_fail says why). */
  group: "tuyas" | "1" | "2";
  purpose: string;
  family: string;
  tags: string[];
  account: "si" | "no" | "opcional" | "desconocido";
  /** false = what you write can be published or used by the site. */
  private: boolean;
  /** Qwen, DeepSeek, z.ai, Meta: configured in webllm; "Conectar" for them is the session check. */
  builtin: boolean;
  daily_cap: number;
  note: string;
  may_fail: string;
  state: CatalogState;
  /** Its name among your AIs when it is connected. */
  provider: string | null;
  when: string;
  reason: string;
  message: string;
  diagnosis_saved: boolean;
}

export interface BatchResult {
  key: string;
  name: string;
  status: "pending" | "running" | "ok" | "sin_conectar" | "no_funciona" | "skipped";
  error: string;
  message: string;
  add_id?: string;
  steps?: AddStep[];
}

export interface Batch {
  batch_id: string;
  status: "permission" | "running" | "done" | "failed";
  keys: string[];
  current: string | null;
  error: string;
  message: string;
  results: BatchResult[];
  done: number;
  connected: number;
}

export interface Catalogo {
  checked: string;
  ais: CatalogAi[];
  batch: Batch | null;
}

/** What a chat can do, read on its page (PLAN-v5 F4). */
export interface FichaModel {
  name: string;
  slug: string;
  rank: number | null;
  /** In the catalog's table (or marked by Iván). */
  known: boolean;
  by_ivan: boolean;
  strongest: boolean;
  /** Same rank as another one: webllm does not guess which is stronger. */
  tie: boolean;
}

export interface Ficha {
  ai: string;
  label: string;
  site: string;
  discovered: boolean;
  when: string | null;
  current_model: string | null;
  models: FichaModel[];
  strongest: string | null;
  strongest_by_ivan: string | null;
  /** Iván chose: never switch this chat's model, use whatever its page has. */
  use_page_model: boolean;
  modes: { name: string; on: boolean; mode: string | null }[];
  plus: string[];
  files: { accept: string; multiple: boolean }[];
  found: { model: boolean; plus: boolean };
  table: { source: string; checked: string; known: string[] };
  taught: string[];
  /** PLAN-v5 F6: every change to where things are on this site, newest first; each can be undone. */
  arreglos: Arreglo[];
  /** The last daily check of this chat. */
  revision: SiteCheck | null;
}

export interface Arreglo {
  index: number;
  when: string;
  /** "la caja de texto", "la respuesta"… */
  what: string;
  /** "tú" or "una IA (z.ai)" */
  by: string;
  why: string;
  active: boolean;
  undone: string | null;
}

export interface SiteCheck {
  site?: string;
  label: string;
  state: "bien" | "reparada" | "sin_sesion" | "verificacion" | "saturada" | "limite" | "bloqueada" | "no_encuentro_la_caja" | "no_se_pudo_abrir";
  when: string;
  repaired_by?: string;
}

export interface Revision {
  when: string | null;
  running: boolean;
  sites: SiteCheck[];
  ok: number;
  total: number;
}

export interface Reparar {
  enabled: boolean;
  ai: string | null;
  ai_label: string | null;
  options: { name: string; label: string }[];
  last: { when: string; site: string; result: string; why?: string }[];
}

/** A chat Iván goes on with by hand in his Chrome, recorded (PLAN-v5 F6). */
export interface Observing {
  tab: number;
  site: string;
  label: string;
  follows: string | null;
  since: string;
}

export interface LocalServer {
  key: string;
  name: string;
  up: boolean;
  installed: boolean;
  models: number;
}

export interface Estado {
  chrome: boolean;
  omniroute: boolean;
  extension_path: string;
  ais: Ai[];
  local_servers: LocalServer[];
  observing?: Observing[];
}

export interface HistoryAnswer {
  target: string;
  label: string;
  provider: string;
  provider_label: string;
  ok: boolean;
  text: string;
  seconds: number;
  error: string;
  code: string;
  /** The conversation's own address on the chat's site ("Continuar en la web"). */
  url?: string;
  by_ivan?: boolean;
  repaired?: boolean;
}

export interface HistoryStep {
  id: string;
  title: string;
  message: string;
  answers: HistoryAnswer[];
  ran: boolean;
}

export interface RunSummary {
  id: string;
  ts: string | null;
  kind: "pregunta" | "cadena" | "web";
  title: string;
  text: string;
  status: string;
  ais: { name: string; label: string; ok: boolean }[];
  lock: boolean;
}

export interface RunDetail {
  id: string;
  ts: string | null;
  kind: "pregunta" | "cadena" | "web";
  title: string;
  template: string;
  text: string;
  status: string;
  steps: HistoryStep[];
  lock: boolean;
  lock_reason: string;
  folder: string;
}

// Events streamed by POST /api/preguntar (see src/webllm_agent/flows.py).
export type FlowEvent =
  | { type: "flow_start"; run_id: string; steps: { id: string; to: string[]; labels: string[] }[] }
  | { type: "target_start"; step: string; target: string; label: string }
  | {
      type: "target_done";
      step: string;
      target: string;
      label: string;
      provider: string;
      provider_label: string;
      ok: boolean;
      text: string;
      seconds: number;
      error: string;
      code: string;
      url?: string;
      repaired?: { ai?: string; roles?: string[] };
    }
  | { type: "flow_done"; run_id: string; status: string; verified: boolean }
  | { type: "error"; code: string; error: string }
  | { type: "step_start" | "step_done" | "target_wait" | "target_fallback"; [key: string]: unknown };

/** "Memoria en Obsidian" (PLAN-v5 F5): where the vault is and how the last write went. */
export type Memoria = {
  dir: string;
  enabled: boolean;
  error: string | null;
  last: string | null;
  conversations: number;
  answers: number;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
  ) {
    super(message);
  }
}

const headers = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };

async function fail(r: Response): Promise<never> {
  let body: { error?: string; code?: string } = {};
  try {
    body = await r.json();
  } catch {
    // not JSON: keep the generic message
  }
  throw new ApiError(body.error ?? `El servidor respondió ${r.status}.`, body.code ?? "error", r.status);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError("No hay conexión con webllm.", "offline", 0);
  }
  if (!r.ok) return fail(r);
  return (await r.json()) as T;
}

const post = <T>(path: string, body: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  estado: () => call<Estado>("/api/estado"),
  reanudar: (ia: string) => post<{ ok: boolean; cleared: boolean }>("/api/reanudar", { ia }),
  /** "Parar todo" (PLAN-v5 D9): every question in progress, from here or from Open WebUI, and its job in Chrome. */
  pararTodo: () => post<{ parados: number; chats: string[] }>("/gw/v1/parar", {}),
  comprobar: (ia: string) => post<{ session: Session }>("/api/comprobar", { ia }),
  conectar: (ia: string) => post<{ session: Session; shown: boolean }>("/api/conectar", { ia }),
  encenderOmniroute: () => post<{ ok: boolean; already: boolean }>("/api/encender-omniroute", {}),
  encenderLocal: (server: string) => post<{ ok: boolean; already: boolean }>("/api/encender-local", { server }),
  anadir: (url: string) => post<AddState>("/api/anadir", { url }),
  anadirEstado: (id: string) => call<AddState>(`/api/anadir/${encodeURIComponent(id)}`),
  quitar: (ia: string) => post<{ ok: boolean }>("/api/quitar", { ia }),
  catalogo: () => call<Catalogo>("/api/catalogo"),
  /** "Conectar varias": the marked ones are tried; `skip` = unmarked (they become "No la quiero"). */
  conectarVarias: (keys: string[], skip: string[] = []) => post<Batch>("/api/conectar-varias", { keys, skip }),
  conectarVariasEstado: (id: string) => call<Batch>(`/api/conectar-varias/${encodeURIComponent(id)}`),
  conectarVariasParar: (id: string) => post<Batch>(`/api/conectar-varias/${encodeURIComponent(id)}/parar`, {}),
  ficha: (ai: string) => call<Ficha>(`/api/ficha/${encodeURIComponent(ai)}`),
  /** Read it on the chat's page: menus opened, read and closed; nothing pressed, nothing sent. */
  descubrir: (ia: string) => post<Ficha>("/api/descubrir", { ia }),
  fichaPotente: (ai: string, model: string | null, page = false) =>
    post<Ficha>(`/api/ficha/${encodeURIComponent(ai)}/potente`, { model, page }),
  /** "Enséñame dónde está": the chat comes forward; Iván's next click there shows where that thing is. */
  ensename: (ia: string, what: "model" | "plus" | "file" | "input" | "send" | "answer") =>
    post<Ficha & { name: string | null }>("/api/ensename", { ia, what }),
  /** Undo one repair or lesson of this chat: the extension stops using it at once. */
  fichaDeshacer: (ai: string, index: number) => post<Ficha>(`/api/ficha/${encodeURIComponent(ai)}/deshacer`, { index }),
  revision: () => call<Revision>("/api/revision"),
  /** "Comprobar ahora": each chat opened and looked at; nothing is sent. */
  revisar: () => post<Revision>("/api/revisar", {}),
  reparar: () => call<Reparar>("/api/reparar"),
  guardarReparar: (enabled: boolean, ai: string | null) => post<Reparar>("/api/reparar", { enabled, ai: ai ?? "" }),
  /** "Continuar en la web": that conversation, in a normal tab of your Chrome, recorded as you go on. */
  continuar: (runId: string, ai?: string) => post<{ ok: boolean; label: string; url: string }>("/api/continuar", { run_id: runId, ai: ai ?? "" }),
  dejarDeRegistrar: (tab?: number) => post<{ ok: boolean }>("/api/dejar-de-registrar", tab ? { tab } : {}),
  fichaOlvidar: (ai: string) => post<Ficha>(`/api/ficha/${encodeURIComponent(ai)}/olvidar`, {}),
  memoria: () => call<Memoria>("/api/memoria"),
  guardarMemoria: (dir: string, enabled: boolean) => post<Memoria>("/api/memoria", { dir, enabled }),
  /** "Reescribir todo": every conversation and answer written again from the journal (hand edits there are lost). */
  reescribirMemoria: () => post<Memoria>("/api/memoria/reescribir", {}),
  /** "Copiar también lo de antes": the questions webllm recorded before the memory was on. */
  memoriaAnteriores: () => post<Memoria>("/api/memoria/anteriores", {}),
  iconUrl: (key: string) => `/api/icono/${encodeURIComponent(key)}?token=${encodeURIComponent(TOKEN)}`,
  historial: (q: string) => call<{ runs: RunSummary[] }>(`/api/historial?q=${encodeURIComponent(q)}`),
  detalle: (id: string) => call<RunDetail>(`/api/historial/${encodeURIComponent(id)}`),
  exportUrl: (id: string) => `/api/historial/${encodeURIComponent(id)}/exportar?token=${encodeURIComponent(TOKEN)}`,
};

/** Ask one or several AIs; ``onEvent`` receives the live progress until the run ends. */
export async function preguntar(
  body: { prompt: string; to: string[]; title?: string },
  onEvent: (e: FlowEvent) => void,
): Promise<void> {
  let r: Response;
  try {
    r = await fetch("/api/preguntar", { method: "POST", headers, body: JSON.stringify(body) });
  } catch {
    throw new ApiError("No hay conexión con webllm.", "offline", 0);
  }
  if (!r.ok || !(r.headers.get("content-type") ?? "").includes("text/event-stream") || !r.body) return fail(r);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as FlowEvent);
      }
    }
  }
}
