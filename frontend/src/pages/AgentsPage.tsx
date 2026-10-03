import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAgents } from "../hooks/useAgents";
import { useToast } from "../hooks/useToast";
import { AgentList } from "../components/agents/AgentList";
import { CreateAgentForm } from "../components/agents/CreateAgentForm";
import { ToastContainer } from "../components/ui/ToastContainer";
import type { CreateAgentPayload } from "../types/agent";

export function AgentsPage() {
  const { agents, loading, error, createAgent, deleteAgent } = useAgents();
  const { toasts, show: showToast, dismiss } = useToast();
  const [showForm, setShowForm] = useState(false);
  const navigate = useNavigate();

  const handleCreate = async (payload: CreateAgentPayload) => {
    const agent = await createAgent(payload);
    navigate(`/agents/${agent.id}`);
  };

  const handleDelete = async (id: string, name: string) => {
    await deleteAgent(id);
    showToast(`Agente "${name}" removido com sucesso!`, "success");
  };

  return (
    <div className="px-8 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Agentes</h2>
          <p className="text-sm text-gray-500 mt-0.5">Gerencie seus agentes de suporte RAG</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
        >
          Novo Agente
        </button>
      </div>

      {loading && <p className="text-sm text-gray-500">Carregando...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && <AgentList agents={agents} onDelete={handleDelete} />}

      {showForm && (
        <CreateAgentForm onSubmit={handleCreate} onClose={() => setShowForm(false)} />
      )}

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
