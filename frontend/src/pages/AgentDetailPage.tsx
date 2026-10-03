import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useAgent } from "../hooks/useAgents";
import { useToast } from "../hooks/useToast";
import { DocumentUpload } from "../components/documents/DocumentUpload";
import { TrainingDocumentsTab } from "../components/documents/TrainingDocumentsTab";
import { ToastContainer } from "../components/ui/ToastContainer";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { IngestResult, FileCompleteInfo } from "../types/document";
import { AGENT_STATUS_STYLES } from "../types/agent";

function EmbeddingsBadge({ useEmbeddings }: { useEmbeddings: boolean }) {
  if (useEmbeddings) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-teal-100 text-teal-800 border border-teal-200">
        <span className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-pulse" />
        Embeddings · Híbrido adaptativo
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200">
      BM25 · Léxico
    </span>
  );
}

type Tab = "upload" | "documents";

export function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { agent, loading, error, refetch } = useAgent(id!);
  const [activeTab, setActiveTab] = useState<Tab>("upload");
  const navigate = useNavigate();
  const { toasts, show: showToast, dismiss } = useToast(5000);

  const handleUploaded = (_result: IngestResult) => {
    refetch();
  };

  const handleAllDone = () => {
    refetch();
    setActiveTab("documents");
  };

  const handleFileComplete = (info: FileCompleteInfo) => {
    if (info.status === "success") {
      showToast(
        `${info.filename} · ${info.chunks ?? 0} chunks criados`,
        "success",
      );
    } else if (info.status === "skipped") {
      showToast(
        `${info.filename} · já ingerido — ignorado`,
        "warning",
      );
    } else {
      showToast(
        `${info.filename} · falhou: ${info.error ?? "erro desconhecido"}`,
        "error",
      );
    }
  };

  if (loading) return <div className="px-8 py-6 text-sm text-gray-500">Carregando...</div>;
  if (error) return <div className="px-8 py-6 text-sm text-red-600">{error}</div>;
  if (!agent) return null;

  return (
    <div className="px-8 py-6 max-w-5xl">
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Link to="/" className="hover:text-gray-700">Agentes</Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">{agent.name}</span>
      </div>

      {/* Card de resumo do agente */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{agent.name}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{agent.description}</p>
          </div>
          <StatusBadge status={agent.status} styles={AGENT_STATUS_STYLES} />
        </div>

        {/* Grade de estatísticas */}
        <div className="mt-4 grid grid-cols-5 gap-4 text-sm">
          <div>
            <p className="text-gray-500 text-xs">Documentos</p>
            <p className="font-medium">{agent.total_documents}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Chunks</p>
            <p className="font-medium">{agent.total_chunks}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Persona</p>
            <p className="font-medium">{agent.persona}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Histórico</p>
            <p className="font-medium">{agent.max_history_messages} msgs</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Chunks RAG</p>
            <p className="font-medium">{agent.max_context_chunks}</p>
          </div>
        </div>

        {/* Linha de capacidades RAG */}
        <div className="mt-3 flex flex-wrap gap-2">
          <EmbeddingsBadge useEmbeddings={agent.use_embeddings} />
          {agent.enable_multiquery && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
              Multiquery ×{agent.multiquery_variants}
            </span>
          )}
          {agent.enable_reranker && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
              Reranker LLM
            </span>
          )}
        </div>

        {/* Prompt do sistema */}
        <div className="mt-4 p-3 bg-gray-50 rounded text-xs text-gray-600 font-mono whitespace-pre-wrap">
          {agent.system_prompt}
        </div>
      </div>

      {/* Abas */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab("upload")}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "upload"
                ? "border-primary-600 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Upload de Documentos
          </button>
          <button
            onClick={() => setActiveTab("documents")}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "documents"
                ? "border-primary-600 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Documentos de Treinamento
          </button>
        </div>
        <div className="p-6">
          {activeTab === "upload" && (
            <DocumentUpload
              agentId={agent.id}
              onUploaded={handleUploaded}
              onAllDone={handleAllDone}
              onFileComplete={handleFileComplete}
            />
          )}
          {activeTab === "documents" && (
            <TrainingDocumentsTab agentId={agent.id} />
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/agents/${agent.id}/chat`)}
          disabled={agent.status !== "ready"}
          className="px-5 py-2.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Testar Chat
        </button>
      </div>
      {agent.status !== "ready" && (
        <p className="mt-2 text-xs text-gray-400">Faça upload de documentos para habilitar o chat.</p>
      )}

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
