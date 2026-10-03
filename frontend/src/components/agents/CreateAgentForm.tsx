import { useState } from "react";
import type { CreateAgentPayload } from "../../types/agent";

interface Props {
  onSubmit: (payload: CreateAgentPayload) => Promise<void>;
  onClose: () => void;
}

export function CreateAgentForm({ onSubmit, onClose }: Props) {
  const [form, setForm] = useState<CreateAgentPayload>({
    name: "",
    description: "",
    system_prompt: "",
    persona: "cordial e objetivo",
    language: "pt-BR",
    max_history_messages: 10,
    max_context_chunks: 5,
    enable_multiquery: false,
    multiquery_variants: 3,
    use_embeddings: false,
    enable_reranker: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.system_prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(form);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar agente");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg flex flex-col max-h-[90vh]">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <h2 className="text-base font-semibold text-gray-900">Novo Agente</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
        <div className="px-6 py-4 space-y-4 overflow-y-auto flex-1">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome *</label>
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              required
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Ex: Suporte Loja X"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
            <input
              name="description"
              value={form.description}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Breve descrição do agente"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt *</label>
            <textarea
              name="system_prompt"
              value={form.system_prompt}
              onChange={handleChange}
              required
              rows={5}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
              placeholder="Você é o assistente de suporte da Loja X..."
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Persona</label>
              <input
                name="persona"
                value={form.persona}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Idioma</label>
              <input
                name="language"
                value={form.language}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Histórico de mensagens</label>
              <input
                type="number"
                min={1}
                max={100}
                value={form.max_history_messages ?? 10}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, max_history_messages: parseInt(e.target.value) || 10 }))
                }
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <p className="mt-1 text-xs text-gray-500">Mensagens anteriores consideradas (1–100).</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Chunks de contexto</label>
              <input
                type="number"
                min={1}
                max={20}
                value={form.max_context_chunks ?? 5}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, max_context_chunks: parseInt(e.target.value) || 5 }))
                }
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <p className="mt-1 text-xs text-gray-500">Trechos recuperados por query (1–20). Mais = melhor recall, mais custo.</p>
            </div>
          </div>
          <div className="border border-gray-200 rounded-lg p-4 space-y-4 bg-gray-50">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Recuperação de Contexto (RAG)</p>

            {/* Alternador de embeddings */}
            <div className={`rounded-lg border-2 p-3 transition-colors ${form.use_embeddings ? "border-teal-400 bg-teal-50" : "border-gray-200 bg-white"}`}>
              <label className="flex items-start gap-3 cursor-pointer">
                <div className="relative mt-0.5 flex-shrink-0">
                  <input
                    type="checkbox"
                    checked={form.use_embeddings ?? false}
                    onChange={(e) => setForm((prev) => ({ ...prev, use_embeddings: e.target.checked }))}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 rounded-full bg-gray-300 transition-colors peer-checked:bg-teal-500
                    after:content-[''] after:absolute after:top-0.5 after:left-0.5
                    after:w-4 after:h-4 after:bg-white after:rounded-full after:shadow
                    after:transition-transform peer-checked:after:translate-x-4" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-800">Embeddings</span>
                    {form.use_embeddings && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-teal-100 text-teal-700 font-medium">Ativo</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                    {form.use_embeddings
                      ? "Busca híbrida ativa, o sistema escolhe automaticamente entre BM25 (termos exatos) e semântico (significado) a cada pergunta."
                      : "Desativado, usa apenas BM25 (busca léxica por termos exatos)."}
                  </p>
                </div>
              </label>
            </div>

            {/* Multiquery */}
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.enable_multiquery ?? false}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, enable_multiquery: e.target.checked }))
                }
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">Multiquery</span>
                <p className="text-xs text-gray-500 mt-0.5">
                  O LLM gera variações da pergunta para ampliar o recall antes de buscar.
                </p>
              </div>
            </label>
            {form.enable_multiquery && (
              <div className="pl-7">
                <label className="block text-xs font-medium text-gray-600 mb-1">Variações por query</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={form.multiquery_variants ?? 3}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, multiquery_variants: parseInt(e.target.value) || 3 }))
                  }
                  className="w-24 border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            )}

            {/* Reranker */}
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.enable_reranker ?? false}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, enable_reranker: e.target.checked }))
                }
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">Reranker (LLM)</span>
                <p className="text-xs text-gray-500 mt-0.5">
                  Recupera mais candidatos e usa o LLM para selecionar os mais relevantes. Aumenta latência.
                </p>
              </div>
            </label>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3 flex-shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
            >
              {submitting ? "Criando..." : "Criar Agente"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
