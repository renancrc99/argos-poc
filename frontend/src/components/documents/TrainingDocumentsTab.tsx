import { useDocuments } from "../../hooks/useDocuments";
import type { DocumentRecord } from "../../types/document";
import { StatusBadge } from "../ui/StatusBadge";
import { formatBytes } from "../../utils/format";

const DOCUMENT_STATUS_STYLES: Record<string, string> = {
  processed: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
  uploaded: "bg-yellow-100 text-yellow-800",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function DocumentRow({ doc }: { doc: DocumentRecord }) {
  return (
    <tr className="border-t border-gray-100 hover:bg-gray-50">
      <td className="py-3 px-4 text-sm font-medium text-gray-900 max-w-xs truncate" title={doc.filename}>
        {doc.filename}
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 whitespace-nowrap">
        {formatBytes(doc.size_bytes)}
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 whitespace-nowrap">
        {doc.content_type.split("/").pop()}
      </td>
      <td className="py-3 px-4 text-sm text-gray-900 font-medium whitespace-nowrap">
        {doc.chunk_stats.count}
      </td>
      <td className="py-3 px-4">
        <div className="flex flex-col gap-0.5 text-xs text-gray-600">
          <span>size: <span className="font-medium text-gray-800">{doc.chunk_size}</span></span>
          <span>overlap: <span className="font-medium text-gray-800">{doc.chunk_overlap}</span></span>
        </div>
      </td>
      <td className="py-3 px-4">
        <div className="flex flex-col gap-0.5 text-xs text-gray-500">
          <span>min: <span className="font-medium text-gray-700">{doc.chunk_stats.min_chars}</span></span>
          <span>max: <span className="font-medium text-gray-700">{doc.chunk_stats.max_chars}</span></span>
          <span>avg: <span className="font-medium text-gray-700">{doc.chunk_stats.avg_chars}</span></span>
        </div>
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 whitespace-nowrap">
        {doc.chunk_stats.total_chars.toLocaleString("pt-BR")}
      </td>
      <td className="py-3 px-4 whitespace-nowrap">
        <StatusBadge status={doc.status} styles={DOCUMENT_STATUS_STYLES} />
      </td>
      <td className="py-3 px-4 text-xs text-gray-400 whitespace-nowrap">
        {formatDate(doc.ingested_at)}
      </td>
      <td className="py-3 px-4">
        <div className="flex flex-col gap-1">
          {doc.file_hash ? (
            <>
              <span
                className="font-mono text-xs text-gray-400 cursor-default"
                title={`file: ${doc.file_hash}\nconfig: ${doc.config_hash}`}
              >
                <span className="text-gray-300 select-none">f:</span> {doc.file_hash.slice(0, 8)}…
              </span>
              <span
                className="font-mono text-xs text-gray-400 cursor-default"
                title={`file: ${doc.file_hash}\nconfig: ${doc.config_hash}`}
              >
                <span className="text-gray-300 select-none">c:</span> {doc.config_hash.slice(0, 8)}…
              </span>
            </>
          ) : (
            <span className="text-xs text-gray-300 italic">—</span>
          )}
        </div>
      </td>
    </tr>
  );
}

export function TrainingDocumentsTab({ agentId }: { agentId: string }) {
  const { documents, loading, error, refetch } = useDocuments(agentId);

  if (loading) {
    return <p className="text-sm text-gray-400 py-4">Carregando documentos...</p>;
  }

  if (error) {
    return (
      <div className="flex items-center justify-between py-4">
        <p className="text-sm text-red-500">{error}</p>
        <button onClick={refetch} className="text-xs text-primary-600 hover:underline">Tentar novamente</button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <p className="text-sm text-gray-400 py-4">
        Nenhum documento ingerido ainda. Faça upload de documentos na seção acima.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500">{documents.length} documento{documents.length !== 1 ? "s" : ""} encontrado{documents.length !== 1 ? "s" : ""}</p>
        <button onClick={refetch} className="text-xs text-primary-600 hover:underline">Atualizar</button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-left">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="py-2 px-4 font-medium">Arquivo</th>
              <th className="py-2 px-4 font-medium">Tamanho</th>
              <th className="py-2 px-4 font-medium">Tipo</th>
              <th className="py-2 px-4 font-medium">Chunks</th>
              <th className="py-2 px-4 font-medium">Params</th>
              <th className="py-2 px-4 font-medium">Tamanho dos Chunks (chars)</th>
              <th className="py-2 px-4 font-medium">Total chars</th>
              <th className="py-2 px-4 font-medium">Status</th>
              <th className="py-2 px-4 font-medium">Ingerido em</th>
              <th className="py-2 px-4 font-medium">Hashes</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
