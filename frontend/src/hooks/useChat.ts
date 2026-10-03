import { useState } from "react";
import { api } from "../api/client";
import type { ChatMessage } from "../types/chat";

export function useChat(agentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async (text: string) => {
    const userMessage: ChatMessage = { role: "user", content: text };
    const updatedHistory = [...messages, userMessage];
    setMessages(updatedHistory);
    setLoading(true);
    setError(null);

    try {
      const response = await api.chat.send(agentId, text, messages);
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.response,
        sources: response.sources,
        tokens: { input: response.input_tokens, output: response.output_tokens },
      };
      setMessages([...updatedHistory, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
      setMessages(messages); // desfaz a mensagem do usuário em caso de erro
    } finally {
      setLoading(false);
    }
  };

  return { messages, loading, error, sendMessage };
}
