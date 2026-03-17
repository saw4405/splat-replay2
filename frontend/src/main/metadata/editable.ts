import type { MetadataUpdate, RecordedVideo } from '../api/types.ts';
import { formatMetadataDateTime, normaliseWeaponSlots, type WeaponSlots } from './shared.ts';

export { normaliseWeaponSlots, type WeaponSlots } from './shared.ts';

type MetadataUpdatePayload = Partial<{
  started_at: string;
  match: string;
  rule: string;
  stage: string;
  rate: string;
  judgement: string;
  kill: number;
  death: number;
  special: number;
  goldMedals: number;
  silverMedals: number;
  allies: string[];
  enemies: string[];
}>;

export interface EditableMetadata {
  gameMode: string;
  startedAt: string;
  match: string;
  rule: string;
  stage: string;
  rate: string;
  judgement: string;
  kill: number;
  death: number;
  special: number;
  goldMedals: number;
  silverMedals: number;
  allies: WeaponSlots;
  enemies: WeaponSlots;
}

const EMPTY_WEAPON_SLOTS: WeaponSlots = ['', '', '', ''];

export function createEmptyEditableMetadata(): EditableMetadata {
  return {
    gameMode: '',
    startedAt: '',
    match: '',
    rule: '',
    stage: '',
    rate: '',
    judgement: '',
    kill: 0,
    death: 0,
    special: 0,
    goldMedals: 0,
    silverMedals: 0,
    allies: [...EMPTY_WEAPON_SLOTS] as WeaponSlots,
    enemies: [...EMPTY_WEAPON_SLOTS] as WeaponSlots,
  };
}

export function cloneEditableMetadata(value: EditableMetadata): EditableMetadata {
  return {
    ...value,
    allies: [...value.allies] as WeaponSlots,
    enemies: [...value.enemies] as WeaponSlots,
  };
}

export function toEditableMetadata(video: RecordedVideo): EditableMetadata {
  return {
    gameMode: video.gameMode ?? '',
    startedAt: formatMetadataDateTime(video.startedAt),
    match: video.match ?? '',
    rule: video.rule ?? '',
    stage: video.stage ?? '',
    rate: video.rate ?? '',
    judgement: video.judgement ?? '',
    kill: video.kill ?? 0,
    death: video.death ?? 0,
    special: video.special ?? 0,
    goldMedals: video.goldMedals ?? 0,
    silverMedals: video.silverMedals ?? 0,
    allies: normaliseWeaponSlots(video.allies),
    enemies: normaliseWeaponSlots(video.enemies),
  };
}

export function toMetadataUpdatePayload(
  metadata: MetadataUpdate | EditableMetadata
): MetadataUpdatePayload {
  return {
    started_at: formatMetadataDateTime(metadata.startedAt),
    match: metadata.match,
    rule: metadata.rule,
    stage: metadata.stage,
    rate: metadata.rate,
    judgement: metadata.judgement,
    kill: metadata.kill,
    death: metadata.death,
    special: metadata.special,
    goldMedals: metadata.goldMedals,
    silverMedals: metadata.silverMedals,
    allies: metadata.allies ? [...metadata.allies] : undefined,
    enemies: metadata.enemies ? [...metadata.enemies] : undefined,
  };
}
