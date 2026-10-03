import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api/client";
import type { Agent, CreateAgentPayload } from "../types/agent";

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.agents.list();
      setAgents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const createAgent = async (payload: CreateAgentPayload): Promise<Agent> => {
    const agent = await api.agents.create(payload);
    setAgents((prev) => [agent, ...prev]);
    return agent;
  };

  const deleteAgent = async (id: string): Promise<void> => {
    await api.agents.delete(id);
    setAgents((prev) => prev.filter((a) => a.id !== id));
  };

  return { agents, loading, error, refetch: fetchAgents, createAgent, deleteAgent };
}

export function useAgent(id: string) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadedOnce = useRef(false);

  const fetchAgent = useCallback(async () => {
    try {
      // Só mostra o spinner de carregamento completo na primeira busca.
      // Chamadas subsequentes de refetch() atualizam os dados silenciosamente em segundo plano
      // pra nenhum filho montado (ex: DocumentUpload) ser desmontado.
      if (!loadedOnce.current) setLoading(true);
      setError(null);
      const data = await api.agents.get(id);
      setAgent(data);
      loadedOnce.current = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agent");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchAgent();
  }, [fetchAgent]);

  return { agent, loading, error, refetch: fetchAgent };
}
