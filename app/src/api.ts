// Talks to the webllm server that serves this page (127.0.0.1:20130).
// The server puts its token in <meta name="webllm-token"> when it sends the page.

const TOKEN = document.querySelector<HTMLMetaElement>('meta[name="webllm-token"]')?.content ?? "";

export type AiState = "lista" | "en_pausa" | "sin_chrome" | "apagada" | "sin_sesion" | "saturada";

export interface Ai {
  name: string;
  label: string;
  kind: "chat" | "api";
  state: AiState;
  detail: string;
  until: number | null;
  url: string | null;
  today: number;
  cap: number | null;
}

export interface Estado {
  chrome: boolean;
  omniroute: boolean;
  extension_path: string;
  ais: Ai[];
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
  kind: "pregunta" | "cadena";
  title: string;
  text: string;
  status: string;
  ais: { name: string; label: string; ok: boolean }[];
  lock: boolean;
}

export interface RunDetail {
  id: string;
  ts: string | null;
  kind: "pregunta" | "cadena";
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
    }
  | { type: "flow_done"; run_id: string; status: string; verified: boolean }
  | { type: "error"; code: string; error: string }
  | { type: "step_start" | "step_done" | "target_wait" | "target_fallback"; [key: string]: unknown };

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
  comprobar: (ia: string) =>
    post<{ session: "lista" | "sin_sesion" | "verificacion" | "sin_chrome" | "desconocido" }>("/api/comprobar", { ia }),
  encenderOmniroute: () => post<{ ok: boolean; already: boolean }>("/api/encender-omniroute", {}),
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
