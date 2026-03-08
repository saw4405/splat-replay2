import type { MetadataUpdate, RecordedVideo } from '../api/types';

export type WeaponSlots = [string, string, string, string];

export interface EditableMetadata {
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

export function normaliseWeaponSlots(
  value: string[] | null | undefined,
  emptyValue = ''
): WeaponSlots {
  const slots = value?.slice(0, 4) ?? [];
  while (slots.length < 4) {
    slots.push(emptyValue);
  }
  return [
    slots[0] ?? emptyValue,
    slots[1] ?? emptyValue,
    slots[2] ?? emptyValue,
    slots[3] ?? emptyValue,
  ];
}

export function createEmptyEditableMetadata(): EditableMetadata {
  return {
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
): MetadataUpdate {
  return {
    ...metadata,
    allies: metadata.allies ? [...metadata.allies] : undefined,
    enemies: metadata.enemies ? [...metadata.enemies] : undefined,
  };
}
