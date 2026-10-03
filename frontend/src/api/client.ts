import type { Agent, CreateAgentPayload } from "../types/agent";
import type { IngestResult, DocumentRecord } from "../types/document";
import type { ChatMessage, ChatResponse } from "../types/chat";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Extrai a mensagem de erro de um corpo de resposta (tenta o campo `detail`, senão cai pro status HTTP).
// Compartilhado entre o fetch de request() e o XMLHttpRequest de documents.upload().
function extractErrorMessage(bodyText: string, status: number): string {
  try {
    const parsed = JSON.parse(bodyText) as { detail?: string };
    return parsed.detail || `HTTP ${status}`;
  } catch {
    return `HTTP ${status}`;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const bodyText = await response.text();
    throw new Error(extractErrorMessage(bodyText, response.status));
  }

  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  agents: {
    list: () => request<Agent[]>("/agents"),
    get: (id: string) => request<Agent>(`/agents/${id}`),
    create: (data: CreateAgentPayload) =>
      request<Agent>("/agents", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request<void>(`/agents/${id}`, { method: "DELETE" }),
  },
  documents: {
    list: (agentId: string) => request<DocumentRecord[]>(`/agents/${agentId}/documents`),
    upload: (
      agentId: string,
      file: File,
      chunkSize?: number,
      chunkOverlap?: number,
      onProgress?: (uploadPct: number, bytesPerSec: number) => void,
    ): Promise<IngestResult> => {
      const MIME_BY_EXT: Record<string, string> = {
        pdf: "application/pdf",
        docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        txt: "text/plain",
        md: "text/markdown",
      };
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      const contentType = MIME_BY_EXT[ext] || file.type || "application/octet-stream";
      const blob = file.type === contentType ? file : new Blob([file], { type: contentType });
      const form = new FormData();
      form.append("file", blob, file.name);
      if (chunkSize !== undefined) form.append("chunk_size", String(chunkSize));
      if (chunkOverlap !== undefined) form.append("chunk_overlap", String(chunkOverlap));

      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_BASE}/agents/${agentId}/documents`);
        const startMs = Date.now();

        xhr.upload.onprogress = (e) => {
          if (!onProgress || !e.lengthComputable || e.total === 0) return;
          const elapsed = (Date.now() - startMs) / 1000;
          const bytesPerSec = elapsed > 0.1 ? e.loaded / elapsed : 0;
          // Bytes enviados = 0–85% do progresso total
          onProgress((e.loaded / e.total) * 85, bytesPerSec);
        };

        xhr.upload.onload = () => {
          // Todos os bytes enviados, o backend agora está processando
          onProgress?.(85, 0);
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try { resolve(JSON.parse(xhr.responseText) as IngestResult); }
            catch { resolve(undefined as unknown as IngestResult); }
          } else {
            reject(new Error(extractErrorMessage(xhr.responseText, xhr.status)));
          }
        };

        xhr.onerror = () => reject(new Error("Falha na conexão"));
        xhr.ontimeout = () => reject(new Error("Timeout"));
        xhr.send(form);
      });
    },
  },
  chat: {
    send: (agentId: string, message: string, history: ChatMessage[]) =>
      request<ChatResponse>(`/agents/${agentId}/chat`, {
        method: "POST",
        body: JSON.stringify({
          message,
          conversation_history: history.map((m) => ({ role: m.role, content: m.content })),
        }),
      }),
  },
};
