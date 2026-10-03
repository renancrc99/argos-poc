import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { IngestResult, FileCompleteInfo } from "../../types/document";
import { formatBytes } from "../../utils/format";

interface Props {
  agentId: string;
  onUploaded: (result: IngestResult) => void;
  onAllDone?: () => void;
  onFileComplete?: (info: FileCompleteInfo) => void;
}

const ACCEPTED = ".pdf,.docx,.txt,.md";

// ── Modo de chunking ──────────────────────────────────────────────────────────

type ChunkMode = "auto" | "preset" | "manual";
type PresetKey = "small" | "medium" | "large";

const PRESETS: Record<PresetKey, { label: string; description: string; chunkSize: number; chunkOverlap: number }> = {
  small:  { label: "Pequeno",  description: "FAQs, artigos curtos, notas",          chunkSize: 512,  chunkOverlap: 64  },
  medium: { label: "Médio",    description: "Documentação geral, manuais técnicos", chunkSize: 1024, chunkOverlap: 128 },
  large:  { label: "Grande",   description: "Livros, relatórios longos, contratos", chunkSize: 2048, chunkOverlap: 256 },
};

const MODES: { value: ChunkMode; label: string; description: string }[] = [
  { value: "auto",   label: "Automático",  description: "Detecta o tamanho ideal com base no total de caracteres do documento" },
  { value: "preset", label: "Predefinido", description: "Escolha entre perfis prontos por tipo de documento" },
  { value: "manual", label: "Manual",      description: "Defina chunk size e overlap manualmente" },
];

// ── Entradas de arquivo ───────────────────────────────────────────────────────

type FileStatus = "uploading" | "success" | "skipped" | "error";
type FilePhase  = "upload" | "processing" | "done";

interface FileEntry {
  id: string;
  file: File;
  status: FileStatus;
  phase: FilePhase;
  progress: number;          // 0–100
  processingFactor: number;  // passo assintótico a cada tick — maior para arquivos pequenos, menor para grandes
  bytesPerSec: number;
  processingStartMs: number;
  processingElapsedMs: number;
  chunks?: number;
  error?: string;
}

// ── Auxiliares ────────────────────────────────────────────────────────────────

function formatSpeed(bps: number): string {
  if (bps <= 0) return "";
  if (bps < 1024) return `${bps.toFixed(0)} B/s`;
  if (bps < 1024 * 1024) return `${(bps / 1024).toFixed(1)} KB/s`;
  return `${(bps / (1024 * 1024)).toFixed(1)} MB/s`;
}

function formatRemaining(remainingBytes: number, bps: number): string {
  if (bps <= 0 || remainingBytes <= 0) return "";
  const secs = remainingBytes / bps;
  if (secs < 5) return "< 5s restante";
  if (secs < 60) return `~${Math.ceil(secs)}s restante`;
  const m = Math.floor(secs / 60);
  const s = Math.ceil(secs % 60);
  return `~${m}m ${s}s restante`;
}

function formatElapsed(ms: number): string {
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

// ── Componente ────────────────────────────────────────────────────────────────

export function DocumentUpload({ agentId, onUploaded, onAllDone, onFileComplete }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  // estado do modo de chunking
  const [chunkMode, setChunkMode] = useState<ChunkMode>("auto");
  const [preset, setPreset] = useState<PresetKey>("medium");
  const [chunkSize, setChunkSize] = useState(1024);
  const [chunkOverlap, setChunkOverlap] = useState(128);

  // estado da lista de arquivos
  const [files, setFiles] = useState<FileEntry[]>([]);

  // Ref estável para onAllDone — evita reexecutar o efeito de "tudo concluído" a cada re-render do pai
  const onAllDoneRef = useRef(onAllDone);
  useEffect(() => { onAllDoneRef.current = onAllDone; }, [onAllDone]);
  const batchDoneCalledRef = useRef(false);

  // Dispara onAllDone exatamente uma vez por lote quando todo arquivo termina
  useEffect(() => {
    if (files.length > 0 && !batchDoneCalledRef.current && files.every((f) => f.status !== "uploading")) {
      batchDoneCalledRef.current = true;
      onAllDoneRef.current?.();
    }
  }, [files]); // sem onAllDone na lista de deps de propósito — usa o ref acima

  // Anima a fase de "processamento": avança assintoticamente em direção a 99%.
  // Cada arquivo usa seu próprio processingFactor, então arquivos grandes animam mais devagar que os pequenos.
  const filesRef = useRef(files);
  filesRef.current = files;

  useEffect(() => {
    const interval = setInterval(() => {
      if (!filesRef.current.some((f) => f.phase === "processing")) return;
      setFiles((prev) =>
        prev.map((f) => {
          if (f.phase !== "processing") return f;
          const newProgress = f.progress + (99 - f.progress) * f.processingFactor;
          const elapsed = f.processingStartMs > 0 ? Date.now() - f.processingStartMs : 0;
          return { ...f, progress: newProgress, processingElapsedMs: elapsed };
        })
      );
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // ── Estado derivado ──────────────────────────────────────────────────────────

  const overlapError =
    chunkMode === "manual" && chunkOverlap >= chunkSize
      ? "Overlap deve ser menor que o chunk size"
      : null;

  const resolveParams = (): { chunkSize?: number; chunkOverlap?: number } => {
    if (chunkMode === "auto") return {};
    if (chunkMode === "preset") return { chunkSize: PRESETS[preset].chunkSize, chunkOverlap: PRESETS[preset].chunkOverlap };
    return { chunkSize, chunkOverlap };
  };

  const anyUploading = files.some((f) => f.status === "uploading");
  const canDrop = !overlapError;

  const overallProgress = files.length > 0
    ? Math.round(files.reduce((sum, f) => sum + f.progress, 0) / files.length)
    : 0;
  const doneCount  = files.filter((f) => f.status !== "uploading").length;
  const totalCount = files.length;
  const allDone    = totalCount > 0 && doneCount === totalCount;
  const hasErrors  = files.some((f) => f.status === "error");
  const hasSkipped = files.some((f) => f.status === "skipped");

  // ── Lógica de upload ─────────────────────────────────────────────────────────

  const uploadEntry = async (entry: FileEntry, params: { chunkSize?: number; chunkOverlap?: number }) => {
    setFiles((prev) =>
      prev.map((f) =>
        f.id === entry.id
          ? { ...f, status: "uploading", phase: "upload", progress: 0, bytesPerSec: 0,
              processingStartMs: 0, processingElapsedMs: 0, error: undefined }
          : f
      )
    );

    try {
      const result = await api.documents.upload(
        agentId,
        entry.file,
        params.chunkSize,
        params.chunkOverlap,
        (uploadPct, bytesPerSec) => {
          setFiles((prev) =>
            prev.map((f) => {
              if (f.id !== entry.id) return f;
              const nowProcessing = uploadPct >= 85;
              const justStartedProcessing = nowProcessing && f.phase === "upload";
              return {
                ...f,
                progress: uploadPct,
                phase: nowProcessing ? "processing" : "upload",
                bytesPerSec: nowProcessing ? f.bytesPerSec : bytesPerSec,
                processingStartMs: justStartedProcessing ? Date.now() : f.processingStartMs,
              };
            })
          );
        }
      );

      const ingestStatus = result?.status === "skipped" ? "skipped" : "success";
      setFiles((prev) =>
        prev.map((f) =>
          f.id === entry.id
            ? { ...f, status: ingestStatus, phase: "done", progress: 100, chunks: result?.chunks_created }
            : f
        )
      );
      // Só notifica o pai quando dado novo foi realmente ingerido (não em caso de skip)
      if (result && ingestStatus === "success") onUploaded(result);
      onFileComplete?.({
        filename: entry.file.name,
        status: ingestStatus,
        chunks: result?.chunks_created,
      });
    } catch (err) {
      const error = err instanceof Error ? err.message : "Falha no upload";
      setFiles((prev) =>
        prev.map((f) =>
          f.id === entry.id ? { ...f, status: "error", phase: "done", progress: 100, error } : f
        )
      );
      onFileComplete?.({ filename: entry.file.name, status: "error", error });
    }
  };

  const makeEntry = (file: File): FileEntry => ({
    id: crypto.randomUUID(),
    file,
    status: "uploading",
    phase: "upload",
    progress: 0,
    // Arquivos maiores processam mais devagar → fator menor pra barra avançar mais devagar.
    // Fórmula: clamp(5000 / fileSize, 0.015, 0.25)
    // Exemplos: 4 KB → 0.25 (rápido), 100 KB → 0.05, 2.4 MB → 0.015 (lento)
    processingFactor: Math.min(0.25, Math.max(0.015, 5_000 / file.size)),
    bytesPerSec: 0,
    processingStartMs: 0,
    processingElapsedMs: 0,
  });

  const addFiles = (newFiles: File[]) => {
    const params = resolveParams();
    const entries = newFiles.map(makeEntry);
    batchDoneCalledRef.current = false;
    setFiles((prev) => [...prev, ...entries]);
    entries.forEach((entry) => uploadEntry(entry, params));
  };

  const handleRetry = (entry: FileEntry) => {
    batchDoneCalledRef.current = false;
    uploadEntry(entry, resolveParams());
  };

  const handleRemove = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length) addFiles(dropped);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    if (selected.length) addFiles(selected);
    e.target.value = "";
  };

  // ── Renderização ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Seletor de modo de chunking */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Modo de chunking</p>
        <div className="space-y-2">
          {MODES.map((mode) => (
            <label
              key={mode.value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                chunkMode === mode.value ? "border-primary-500 bg-primary-50" : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <input
                type="radio"
                name="chunkMode"
                value={mode.value}
                checked={chunkMode === mode.value}
                onChange={() => setChunkMode(mode.value)}
                className="mt-0.5 accent-primary-600"
              />
              <div>
                <span className={`text-sm font-medium ${chunkMode === mode.value ? "text-primary-700" : "text-gray-700"}`}>
                  {mode.label}
                </span>
                <p className="text-xs text-gray-500 mt-0.5">{mode.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Cards de perfis predefinidos */}
      {chunkMode === "preset" && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-2">Perfil do documento</p>
          <div className="grid grid-cols-3 gap-2">
            {(Object.entries(PRESETS) as [PresetKey, typeof PRESETS[PresetKey]][]).map(([key, p]) => (
              <button
                key={key}
                type="button"
                onClick={() => setPreset(key)}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  preset === key ? "border-primary-500 bg-primary-50" : "border-gray-200 bg-white hover:border-gray-300"
                }`}
              >
                <p className={`text-sm font-semibold ${preset === key ? "text-primary-700" : "text-gray-800"}`}>{p.label}</p>
                <p className="text-xs text-gray-500 mt-0.5 leading-snug">{p.description}</p>
                <p className="text-xs text-gray-400 mt-1.5 font-mono">{p.chunkSize} / {p.chunkOverlap}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Campos manuais */}
      {chunkMode === "manual" && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Tamanho do Chunk (chars)</label>
            <input
              type="number" min={64} max={4096} step={64}
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Overlap (chars)</label>
            <input
              type="number" min={0} max={chunkSize - 1} step={16}
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
              className={`w-full border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                overlapError ? "border-red-400" : "border-gray-300"
              }`}
            />
            {overlapError && <p className="mt-0.5 text-xs text-red-500">{overlapError}</p>}
          </div>
        </div>
      )}

      {/* Área de arrastar e soltar */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => canDrop && inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          !canDrop
            ? "border-gray-200 opacity-50 cursor-not-allowed"
            : dragging
            ? "border-primary-500 bg-primary-50 cursor-pointer"
            : "border-gray-300 hover:border-gray-400 cursor-pointer"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          multiple
          className="hidden"
          onChange={handleChange}
          disabled={!canDrop}
        />
        <p className="text-sm text-gray-600">
          {anyUploading ? "Processando..." : "Arraste arquivos aqui ou clique para selecionar"}
        </p>
        <p className="text-xs text-gray-400 mt-1">PDF, DOCX, TXT, MD · múltiplos arquivos simultâneos</p>
      </div>

      {/* Barra de progresso geral */}
      {files.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
              {allDone
                ? hasErrors
                  ? "Concluído com erros"
                  : hasSkipped
                  ? "Concluído (alguns arquivos já existiam)"
                  : "Todos os arquivos processados"
                : "Processando arquivos..."}
            </span>
            <span className={`text-xs font-medium tabular-nums ${
              allDone
                ? hasErrors ? "text-red-600" : hasSkipped ? "text-amber-600" : "text-green-600"
                : "text-primary-600"
            }`}>
              {doneCount} / {totalCount} · {overallProgress}%
            </span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                allDone
                  ? hasErrors ? "bg-red-400" : hasSkipped ? "bg-amber-400" : "bg-green-500"
                  : "bg-primary-600"
              }`}
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Lista de arquivos */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((entry) => (
            <div
              key={entry.id}
              className={`p-3 rounded-lg border text-sm ${
                entry.status === "success"
                  ? "border-green-200 bg-green-50"
                  : entry.status === "skipped"
                  ? "border-amber-200 bg-amber-50"
                  : entry.status === "error"
                  ? "border-red-200 bg-red-50"
                  : "border-gray-200 bg-gray-50"
              }`}
            >
              {/* Linha superior: ícone + nome + ações */}
              <div className="flex items-center gap-3">
                {/* Ícone de status */}
                <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                  {entry.status === "uploading" && (
                    <svg className="animate-spin text-primary-500 w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                  )}
                  {entry.status === "success" && (
                    <svg className="text-green-500 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {entry.status === "skipped" && (
                    <svg className="text-amber-500 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 9l3 3-3 3M6 9l3 3-3 3" />
                    </svg>
                  )}
                  {entry.status === "error" && (
                    <svg className="text-red-500 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                </div>

                {/* Informações do arquivo */}
                <div className="flex-1 min-w-0">
                  <p className="truncate font-medium text-gray-800">{entry.file.name}</p>
                  <p className="text-xs text-gray-400">
                    {formatBytes(entry.file.size)}
                    {entry.status === "success" && entry.chunks !== undefined && (
                      <span className="ml-2 text-green-600">{entry.chunks} chunks criados</span>
                    )}
                    {entry.status === "skipped" && (
                      <span className="ml-2 text-amber-600">Já ingerido com estas configurações — ignorado</span>
                    )}
                    {entry.status === "error" && (
                      <span className="ml-2 text-red-600">{entry.error}</span>
                    )}
                  </p>
                </div>

                {/* Ações */}
                <div className="flex-shrink-0 flex items-center gap-2">
                  {entry.status === "error" && (
                    <button
                      onClick={() => handleRetry(entry)}
                      className="text-xs px-2 py-1 rounded bg-red-100 text-red-700 hover:bg-red-200 transition-colors font-medium"
                    >
                      Tentar novamente
                    </button>
                  )}
                  {entry.status !== "uploading" && (
                    <button
                      onClick={() => handleRemove(entry.id)}
                      className="text-gray-400 hover:text-gray-600 transition-colors text-lg leading-none"
                      title="Remover da lista"
                    >
                      &times;
                    </button>
                  )}
                </div>
              </div>

              {/* Barra de progresso por arquivo (só durante o upload) */}
              {entry.status === "uploading" && (
                <div className="mt-2 pl-8">
                  {/* Rótulo da fase + velocidade */}
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-400">
                      {entry.phase === "upload"
                        ? entry.bytesPerSec > 0
                          ? `${formatSpeed(entry.bytesPerSec)} · ${formatRemaining(
                              entry.file.size * (1 - Math.min(entry.progress, 85) / 85),
                              entry.bytesPerSec
                            )}`
                          : "Enviando..."
                        : entry.processingElapsedMs > 0
                        ? `Processando... ${formatElapsed(entry.processingElapsedMs)}`
                        : "Processando..."}
                    </span>
                    <span className="text-xs font-medium tabular-nums text-primary-600">
                      {Math.round(entry.progress)}%
                    </span>
                  </div>
                  {/* Barra */}
                  <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-300 ${
                        entry.phase === "processing" ? "bg-secondary" : "bg-primary-500"
                      }`}
                      style={{ width: `${entry.progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
