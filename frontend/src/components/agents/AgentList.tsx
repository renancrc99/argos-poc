import { useState } from "react";
import { Link } from "react-router-dom";
import { type Agent, AGENT_STATUS_STYLES } from "../../types/agent";
import { StatusBadge } from "../ui/StatusBadge";

interface Props {
  agents: Agent[];
  onDelete: (id: string, name: string) => Promise<void>;
}

function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
    </svg>
  );
}

function AgentCard({ agent, onDelete }: { agent: Agent; onDelete: (id: string, name: string) => Promise<void> }) {
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const handleDeleteClick = () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setDeleting(true);
    onDelete(agent.id, agent.name).catch(() => setDeleting(false));
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 flex flex-col gap-3">
      {/* Cabeçalho: nome + status à esquerda, botão de deletar à direita */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 truncate">{agent.name}</h3>
          <StatusBadge status={agent.status} styles={AGENT_STATUS_STYLES} />
        </div>
        <button
          onClick={handleDeleteClick}
          onBlur={() => setConfirming(false)}
          disabled={deleting}
          title={confirming ? "Clique novamente para confirmar" : "Deletar agente"}
          className={`flex-shrink-0 flex items-center gap-1 px-2 py-1 rounded text-xs font-medium border transition-colors disabled:opacity-50 ${
            confirming
              ? "bg-red-600 text-white border-red-600 hover:bg-red-700"
              : "text-red-500 border-red-200 hover:bg-red-50"
          }`}
        >
          <TrashIcon />
          {confirming ? "Confirmar?" : "Deletar"}
        </button>
      </div>

      <p className="text-sm text-gray-500 line-clamp-2 flex-1">{agent.description}</p>

      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span>{agent.total_documents} doc(s)</span>
        <span>{agent.total_chunks} chunks</span>
      </div>

      <div className="flex gap-2 pt-1 border-t border-gray-100">
        <Link
          to={`/agents/${agent.id}`}
          className="flex-1 text-center text-xs font-medium text-primary-600 hover:text-primary-800 py-1.5 rounded border border-primary-200 hover:bg-primary-50 transition-colors"
        >
          Documentos / Config
        </Link>
        <Link
          to={`/agents/${agent.id}/chat`}
          className={`flex-1 text-center text-xs font-medium py-1.5 rounded border transition-colors ${
            agent.status === "ready"
              ? "text-green-700 border-green-200 hover:bg-green-50"
              : "text-gray-400 border-gray-200 cursor-not-allowed pointer-events-none"
          }`}
        >
          Testar Chat
        </Link>
      </div>
    </div>
  );
}

export function AgentList({ agents, onDelete }: Props) {
  if (agents.length === 0) {
    return (
      <p className="text-gray-500 text-sm text-center py-12">
        Nenhum agente criado ainda. Clique em "Novo Agente" para começar.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} onDelete={onDelete} />
      ))}
    </div>
  );
}
