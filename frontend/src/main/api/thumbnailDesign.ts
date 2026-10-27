export type ThumbnailSource =
  | 'win_lose'
  | 'rate'
  | 'match'
  | 'rule_label'
  | 'rule_icon'
  | 'stages'
  | 'highlights'
  | 'overlay'
  | 'text'
  | 'shape'
  | 'image';

export interface ThumbnailElement {
  id: string;
  name: string;
  source: ThumbnailSource;
  visible: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  template: string;
  asset: string;
  font: string;
  font_size: number;
  color: string;
  auto_color: boolean;
  outline_color: string;
  outline_width: number;
  center: boolean;
  shape: 'rectangle' | 'rounded_rectangle' | 'ellipse';
  radius: number;
  opacity: number;
}

export interface ThumbnailDesign {
  version: 1;
  background: { source: 'result' | 'image'; asset: string; x: number; y: number; scale: number };
  elements: ThumbnailElement[];
}

export interface ThumbnailBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}
export interface ThumbnailPreview {
  image: string;
  layout: Record<string, ThumbnailBounds>;
}

export interface ThumbnailAsset {
  id: string;
  name: string;
  kind: 'image' | 'font';
  protected: boolean;
}
export interface ThumbnailCatalog {
  default_design: ThumbnailDesign;
  assets: ThumbnailAsset[];
  variables: Record<string, string | number>;
}

async function checked(response: Response): Promise<Response> {
  if (response.ok) return response;
  const data = (await response.json().catch(() => ({
    detail: 'サーバーの応答を読み取れませんでした。もう一度お試しください。',
  }))) as { detail?: string | { msg: string }[] };
  throw new Error(
    typeof data.detail === 'string'
      ? data.detail
      : data.detail?.map((e) => e.msg).join(' / ') ||
          'サムネイルの処理に失敗しました。もう一度お試しください。'
  );
}

export async function getThumbnailCatalog(): Promise<ThumbnailCatalog> {
  return (await checked(await fetch('/api/thumbnail-design', { cache: 'no-store' }))).json();
}

export async function renderThumbnail(
  design: ThumbnailDesign,
  scenario: string,
  signal?: AbortSignal
): Promise<ThumbnailPreview> {
  return (
    await checked(
      await fetch('/api/thumbnail-design/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ design, scenario, include_layout: true }),
        signal,
      })
    )
  ).json();
}

export async function uploadThumbnail(file: File): Promise<string> {
  const data = (await (
    await checked(await fetch('/api/thumbnail-design/assets', { method: 'POST', body: file }))
  ).json()) as { id: string };
  return data.id;
}

export async function deleteThumbnail(asset_id: string, draft: ThumbnailDesign): Promise<void> {
  await checked(
    await fetch('/api/thumbnail-design/assets/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_id, draft }),
    })
  );
}

export function thumbnailAssetUrl(id: string): string {
  return `/api/thumbnail-design/assets/${id.split('/').map(encodeURIComponent).join('/')}`;
}

export function newThumbnailElement(source: 'text' | 'shape' | 'image'): ThumbnailElement {
  return {
    id:
      globalThis.crypto?.randomUUID?.() ??
      `element-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`,
    name: { text: '文字', shape: '図形', image: '画像' }[source],
    source,
    visible: true,
    x: 200,
    y: 200,
    width: source === 'text' ? 0 : 400,
    height: source === 'text' ? 0 : 200,
    template: source === 'text' ? 'テキスト' : '',
    asset: '',
    font: 'Paintball_Beta.otf',
    font_size: 70,
    color: '#ffffff',
    auto_color: false,
    outline_color: '#000000',
    outline_width: 0,
    center: false,
    shape: 'rectangle',
    radius: 40,
    opacity: 1,
  };
}
