export interface IngestResult {
  agent_id: string;
  document_id: string;
  filename: string;
  chunks_created: number;
  status: "processed" | "skipped";
  file_hash: string;
  config_hash: string;
}

export interface ChunkStats {
  count: number;
  min_chars: number;
  max_chars: number;
  avg_chars: number;
  total_chars: number;
}

export interface DocumentRecord {
  id: string;
  agent_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  s3_key: string;
  status: "uploaded" | "processed" | "error";
  chunk_size: number;
  chunk_overlap: number;
  chunk_count: number;
  chunk_stats: ChunkStats;
  ingested_at: string;
  file_hash: string;
  config_hash: string;
}

export interface FileCompleteInfo {
  filename: string;
  status: "success" | "skipped" | "error";
  chunks?: number;
  error?: string;
}
