export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  tokens?: { input: number; output: number };
}

export interface ChatSource {
  source: string;
  page: number | null;
  score: number;
  snippet: string;
}

export interface ChatResponse {
  response: string;
  sources: ChatSource[];
  input_tokens: number;
  output_tokens: number;
  model: string;
}
