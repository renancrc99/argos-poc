import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { DocumentRecord } from "../types/document";

export function useDocuments(agentId: string) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.documents.list(agentId);
      setDocuments(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar documentos");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => { fetch(); }, [fetch]);

  return { documents, loading, error, refetch: fetch };
}
