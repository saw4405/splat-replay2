import { copyFileSync, linkSync, mkdirSync, writeFileSync } from 'node:fs';
import { extname, join } from 'node:path';

import {
  loadSidecarMetadata,
  type E2EEnvironment,
  type ReplayAsset,
  type SidecarMetadata,
} from './e2eEnv';

type SeedableSidecarMetadata = SidecarMetadata & {
  started_at?: string | null;
};

export type RecordedSeedMetadata = Omit<SeedableSidecarMetadata, 'scenario'>;

export type RecordedSeedSource = {
  asset: ReplayAsset;
  fileStem?: string;
  metadataOverride?: Partial<RecordedSeedMetadata>;
};

export type SeededRecordedVideo = {
  asset: ReplayAsset;
  videoPath: string;
  metadataPath: string;
  metadata: RecordedSeedMetadata;
};

function materializeRecordedVideo(sourcePath: string, targetPath: string): void {
  try {
    linkSync(sourcePath, targetPath);
  } catch {
    copyFileSync(sourcePath, targetPath);
  }
}

function buildRecordedSeedMetadata(source: RecordedSeedSource): RecordedSeedMetadata {
  const sidecar = loadSidecarMetadata(source.asset) as SeedableSidecarMetadata | null;
  if (!sidecar) {
    throw new Error(`Recorded seed metadata was not found for replay asset: ${source.asset.name}`);
  }

  const { scenario: _scenario, ...baseMetadata } = sidecar;
  const metadata = {
    ...baseMetadata,
    ...(source.metadataOverride ?? {}),
  } satisfies RecordedSeedMetadata;

  if (!metadata.started_at) {
    throw new Error(`Recorded seed metadata requires started_at: ${source.asset.name}`);
  }

  return metadata;
}

function resolveFileStem(source: RecordedSeedSource, countsByAssetId: Map<string, number>): string {
  if (source.fileStem) {
    return source.fileStem;
  }

  const nextCount = (countsByAssetId.get(source.asset.id) ?? 0) + 1;
  countsByAssetId.set(source.asset.id, nextCount);
  return nextCount === 1 ? source.asset.id : `${source.asset.id}-${nextCount}`;
}

export function seedRecordedVideos(
  environment: E2EEnvironment,
  sources: RecordedSeedSource[]
): SeededRecordedVideo[] {
  const recordedDir = join(environment.storageDir, 'recorded');
  const countsByAssetId = new Map<string, number>();

  mkdirSync(recordedDir, { recursive: true });

  return sources.map((source) => {
    const fileStem = resolveFileStem(source, countsByAssetId);
    const videoPath = join(recordedDir, `${fileStem}${extname(source.asset.videoPath)}`);
    const metadataPath = join(recordedDir, `${fileStem}.json`);
    const metadata = buildRecordedSeedMetadata(source);

    materializeRecordedVideo(source.asset.videoPath, videoPath);
    writeFileSync(metadataPath, JSON.stringify(metadata, null, 2), 'utf-8');

    return {
      asset: source.asset,
      videoPath,
      metadataPath,
      metadata,
    };
  });
}
