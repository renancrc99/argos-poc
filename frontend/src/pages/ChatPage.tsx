import { useParams, Link } from "react-router-dom";
import { useChat } from "../hooks/useChat";
import { useAgent } from "../hooks/useAgents";
import { ChatWindow } from "../components/chat/ChatWindow";

export function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const { agent } = useAgent(id!);
  const { messages, loading, error, sendMessage } = useChat(id!);

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-3 border-b border-gray-200 bg-white flex items-center gap-3">
        <Link to={`/agents/${id}`} className="text-sm text-primary-600 hover:underline">
          &larr; Voltar
        </Link>
        <div className="h-4 border-l border-gray-200" />
        <div>
          <p className="text-sm font-semibold text-gray-900">{agent?.name ?? "Carregando..."}</p>
          <p className="text-xs text-gray-500">Chat RAG</p>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <ChatWindow
          messages={messages}
          loading={loading}
          error={error}
          onSend={sendMessage}
          maxHistoryMessages={agent?.max_history_messages}
        />
      </div>
    </div>
  );
}
