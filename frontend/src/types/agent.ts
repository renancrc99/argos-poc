export interface Agent {
  id: string;
  name: string;
  description: string;
  status: "created" | "ready" | "error";
  system_prompt: string;
  persona: string;
  language: string;
  total_documents: number;
  total_chunks: number;
  created_at: string;
  max_history_messages: number;
  max_context_chunks: number;
  enable_multiquery: boolean;
  multiquery_variants: number;
  use_embeddings: boolean;
  search_mode: "bm25" | "semantic" | "hybrid";
  enable_reranker: boolean;
}

export const AGENT_STATUS_STYLES: Record<Agent["status"], string> = {
  created: "bg-yellow-100 text-yellow-800",
  ready: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
};

export interface CreateAgentPayload {
  name: string;
  description: string;
  system_prompt: string;
  persona?: string;
  language?: string;
  max_history_messages?: number;
  max_context_chunks?: number;
  enable_multiquery?: boolean;
  multiquery_variants?: number;
  use_embeddings?: boolean;
  search_mode?: "bm25" | "semantic" | "hybrid";
  enable_reranker?: boolean;
}
