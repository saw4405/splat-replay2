import { JSON_HEADERS, safeReadText } from './utils.ts';
import type { SubtitleData } from './types.ts';

export interface ImportedBattle {
  id: string;
  start_seconds: number;
  end_seconds: number;
  segments: [number, number][];
  selected: boolean;
  metadata: Record<string, string | number | string[] | number[] | null>;
  title: string | null;
  description: string | null;
  clip_ready: boolean;
  duration_seconds: number;
  has_thumbnail: boolean;
  has_subtitle: boolean;
  evidence_regions?: Record<string, Record<string, [number, number, number, number]>>;
  evidence_sizes?: Record<string, [number, number]>;
  evidence_assets?: Partial<Record<string, string>>;
  evidence_seconds?: Partial<Record<string, number>>;
}

export type ImportedJobState =
  | 'queued'
  | 'scanning'
  | 'ready'
  | 'editing'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface ImportedOutput {
  id: string;
  title: string | null;
  description: string | null;
  candidate_ids: string[];
  has_thumbnail: boolean;
  has_subtitle: boolean;
}
export interface ImportedVideoJob {
  output_directory?: string | null;
  id: string;
  source_name: string;
  source_started_at?: string | null;
  source_started_at_inferred?: boolean;
  outputs?: ImportedOutput[];
  source_suffix: string;
  state: ImportedJobState;
  progress_percent: number;
  duration_seconds: number | null;
  has_audio: boolean | null;
  candidates: ImportedBattle[];
  error: string | null;
  title: string | null;
  description: string | null;
  created_at: string;
  has_output: boolean;
  has_thumbnail: boolean;
  has_subtitle: boolean;
  output_id: string | null;
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error((await safeReadText(response)) || '動画の取込に失敗しました');
  }
  return (await response.json()) as T;
}

export function uploadImportedVideo(
  file: File,
  onProgress: (percent: number) => void,
  signal?: AbortSignal
): Promise<ImportedVideoJob> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const cleanup = (): void => signal?.removeEventListener('abort', abortRequest);
    const abortRequest = (): void => request.abort();
    if (signal?.aborted) {
      reject(new Error('動画の送信を中止しました'));
      return;
    }
    signal?.addEventListener('abort', abortRequest, { once: true });
    request.open('POST', '/api/imported-videos');
    request.setRequestHeader('Content-Type', 'application/octet-stream');
    request.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress((event.loaded / event.total) * 100);
    };
    request.onerror = () => {
      cleanup();
      reject(new Error('動画を送信できませんでした'));
    };
    request.onabort = () => {
      cleanup();
      reject(new Error('動画の送信を中止しました'));
    };
    request.onload = () => {
      cleanup();
      if (request.status < 200 || request.status >= 300) {
        try {
          const error = JSON.parse(request.responseText) as { detail?: string };
          reject(new Error(error.detail || '動画の取込に失敗しました'));
        } catch {
          reject(new Error('動画の取込に失敗しました'));
        }
        return;
      }
      resolve(JSON.parse(request.responseText) as ImportedVideoJob);
    };
    request.send(file);
  });
}

export function listImportedVideos(): Promise<ImportedVideoJob[]> {
  return jsonRequest('/api/imported-videos');
}

export function getImportedVideo(jobId: string): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}`);
}

export function updateImportedSelection(
  jobId: string,
  candidateIds: string[]
): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}/selection`, {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });
}

export function updateImportedCandidate(
  jobId: string,
  candidateId: string,
  metadata: Record<string, string | number | string[] | null>
): Promise<ImportedVideoJob> {
  return jsonRequest(
    `/api/imported-videos/${encodeURIComponent(jobId)}/candidates/${encodeURIComponent(candidateId)}`,
    {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify({ metadata }),
    }
  );
}

export function getImportedCandidateSubtitle(
  jobId: string,
  candidateId: string
): Promise<SubtitleData> {
  return jsonRequest(
    `/api/imported-videos/${encodeURIComponent(jobId)}/candidates/${encodeURIComponent(candidateId)}/subtitle`
  );
}

export function updateImportedCandidateSubtitle(
  jobId: string,
  candidateId: string,
  data: SubtitleData
): Promise<SubtitleData> {
  return jsonRequest(
    `/api/imported-videos/${encodeURIComponent(jobId)}/candidates/${encodeURIComponent(candidateId)}/subtitle`,
    {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(data),
    }
  );
}

export function updateImportedTitleDescription(
  jobId: string,
  title: string,
  description: string
): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify({ title, description }),
  });
}

export function startImportedEdit(jobId: string): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}/edit`, {
    method: 'POST',
  });
}

export function cancelImportedJob(jobId: string): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
}

export function retryImportedScan(jobId: string): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}/scan`, {
    method: 'POST',
  });
}

export function importedAssetUrl(jobId: string, asset: string): string {
  return `/api/imported-videos/${encodeURIComponent(jobId)}/assets/${asset}`;
}

export function importedAssetDownloadUrl(jobId: string, asset: string): string {
  return `${importedAssetUrl(jobId, asset)}?download=true`;
}

export function updateImportedOutput(
  jobId: string,
  outputId: string,
  title: string,
  description: string
): Promise<ImportedVideoJob> {
  return jsonRequest(
    `/api/imported-videos/${encodeURIComponent(jobId)}/outputs/${encodeURIComponent(outputId)}`,
    { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ title, description }) }
  );
}
export function updateImportedSourceTime(
  jobId: string,
  startedAt: string
): Promise<ImportedVideoJob> {
  return jsonRequest(`/api/imported-videos/${encodeURIComponent(jobId)}/source-time`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify({ started_at: startedAt }),
  });
}
