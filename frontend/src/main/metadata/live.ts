import type { EditableMetadata } from './editable';
import {
  normaliseMedalCount,
  normaliseMedalPair,
  normaliseWeaponSlots,
  type WeaponSlots,
} from './shared';

export type { WeaponSlots } from './shared';

type MedalField = 'gold_medals' | 'silver_medals';

export interface LiveMetadataState {
  game_mode: string;
  stage: string;
  started_at: string;
  match: string;
  rule: string;
  rate: string;
  judgement: string;
  kill: number;
  death: number;
  special: number;
  gold_medals: number;
  silver_medals: number;
  allies: WeaponSlots;
  enemies: WeaponSlots;
}

export type LiveMetadataPayload = Partial<{
  game_mode: string;
  stage: string | null;
  started_at: string | null;
  match: string | null;
  rule: string | null;
  rate: string | null;
  judgement: string | null;
  kill: number;
  death: number;
  special: number;
  gold_medals: number;
  silver_medals: number;
  allies: string[];
  enemies: string[];
}>;

export type LiveMetadataUpdatePayload = Record<string, string | number | string[] | null>;

export type LiveManualEditState = Record<keyof LiveMetadataState, boolean>;

export type LiveMetadataUpdateResult = {
  metadata: LiveMetadataState;
  updatedFields: string[];
  skippedFields: string[];
};

const EMPTY_WEAPON_SLOTS: WeaponSlots = ['', '', '', ''];

export function createEmptyLiveMetadataState(): LiveMetadataState {
  return {
    game_mode: '',
    started_at: '',
    match: '',
    rule: '',
    rate: '',
    judgement: '',
    stage: '',
    kill: 0,
    death: 0,
    special: 0,
    gold_medals: 0,
    silver_medals: 0,
    allies: [...EMPTY_WEAPON_SLOTS] as WeaponSlots,
    enemies: [...EMPTY_WEAPON_SLOTS] as WeaponSlots,
  };
}

export function createEmptyLiveManualEditState(): LiveManualEditState {
  return {
    game_mode: false,
    started_at: false,
    match: false,
    rule: false,
    rate: false,
    judgement: false,
    stage: false,
    kill: false,
    death: false,
    special: false,
    gold_medals: false,
    silver_medals: false,
    allies: false,
    enemies: false,
  };
}

function toNullableString(value: string): string | null {
  return value === '' ? null : value;
}

export function toEditableLiveMetadata(metadata: LiveMetadataState): EditableMetadata {
  return {
    gameMode: metadata.game_mode,
    startedAt: metadata.started_at,
    match: metadata.match,
    rule: metadata.rule,
    stage: metadata.stage,
    rate: metadata.rate,
    judgement: metadata.judgement,
    kill: metadata.kill,
    death: metadata.death,
    special: metadata.special,
    goldMedals: metadata.gold_medals,
    silverMedals: metadata.silver_medals,
    allies: [...metadata.allies] as WeaponSlots,
    enemies: [...metadata.enemies] as WeaponSlots,
  };
}

export function toLiveMetadataState(metadata: EditableMetadata): LiveMetadataState {
  const normalisedMedals = normaliseMedalPair(metadata.goldMedals, metadata.silverMedals);
  return {
    game_mode: metadata.gameMode,
    started_at: metadata.startedAt,
    match: metadata.match,
    rule: metadata.rule,
    rate: metadata.rate,
    judgement: metadata.judgement,
    stage: metadata.stage,
    kill: metadata.kill,
    death: metadata.death,
    special: metadata.special,
    gold_medals: normalisedMedals.goldMedals,
    silver_medals: normalisedMedals.silverMedals,
    allies: [...metadata.allies] as WeaponSlots,
    enemies: [...metadata.enemies] as WeaponSlots,
  };
}

export function normaliseEditedLiveMedalField(
  metadata: LiveMetadataState,
  field: MedalField
): LiveMetadataState {
  const otherField: MedalField = field === 'gold_medals' ? 'silver_medals' : 'gold_medals';
  const otherValue = normaliseMedalCount(metadata[otherField]);
  const maxCurrent = 3 - otherValue;
  const nextValue = Math.min(normaliseMedalCount(metadata[field]), maxCurrent);
  return {
    ...metadata,
    [field]: nextValue,
    [otherField]: otherValue,
  };
}

export function applyIncomingLiveMetadata(
  metadata: LiveMetadataState,
  manuallyEdited: LiveManualEditState,
  data: LiveMetadataPayload
): LiveMetadataUpdateResult {
  const updatedFields: string[] = [];
  const skippedFields: string[] = [];
  const nextMetadata: LiveMetadataState = {
    ...metadata,
    allies: [...metadata.allies] as WeaponSlots,
    enemies: [...metadata.enemies] as WeaponSlots,
  };

  const syncField = <K extends keyof LiveMetadataState>(
    field: K,
    nextValue: LiveMetadataState[K]
  ): void => {
    if (!manuallyEdited[field]) {
      nextMetadata[field] = nextValue;
      updatedFields.push(field);
      return;
    }
    skippedFields.push(`${field} (手動編集済み)`);
  };

  syncField('game_mode', data.game_mode ?? '');
  syncField('started_at', data.started_at ?? '');
  syncField('match', data.match ?? '');
  syncField('rule', data.rule ?? '');
  syncField('rate', data.rate ?? '');
  syncField('judgement', data.judgement ?? '');
  syncField('stage', data.stage ?? '');
  syncField('kill', data.kill ?? 0);
  syncField('death', data.death ?? 0);
  syncField('special', data.special ?? 0);

  const nextGoldMedals = !manuallyEdited.gold_medals
    ? (data.gold_medals ?? metadata.gold_medals)
    : metadata.gold_medals;
  const nextSilverMedals = !manuallyEdited.silver_medals
    ? (data.silver_medals ?? metadata.silver_medals)
    : metadata.silver_medals;
  const normalisedMedals = normaliseMedalPair(nextGoldMedals, nextSilverMedals);
  syncField('gold_medals', normalisedMedals.goldMedals);
  syncField('silver_medals', normalisedMedals.silverMedals);
  syncField('allies', normaliseWeaponSlots(data.allies));
  syncField('enemies', normaliseWeaponSlots(data.enemies));

  return {
    metadata: nextMetadata,
    updatedFields,
    skippedFields,
  };
}

export function buildLiveMetadataPayload(
  metadata: LiveMetadataState,
  manuallyEdited: LiveManualEditState
): LiveMetadataUpdatePayload {
  const payload: LiveMetadataUpdatePayload = {};

  if (manuallyEdited.game_mode && metadata.game_mode) {
    payload.game_mode = metadata.game_mode;
  }
  if (manuallyEdited.started_at) {
    payload.started_at = toNullableString(metadata.started_at);
  }
  if (manuallyEdited.match) {
    payload.match = toNullableString(metadata.match);
  }
  if (manuallyEdited.rule) {
    payload.rule = toNullableString(metadata.rule);
  }
  if (manuallyEdited.rate) {
    payload.rate = toNullableString(metadata.rate);
  }
  if (manuallyEdited.judgement) {
    payload.judgement = toNullableString(metadata.judgement);
  }
  if (manuallyEdited.stage) {
    payload.stage = toNullableString(metadata.stage);
  }
  if (manuallyEdited.kill) {
    payload.kill = metadata.kill;
  }
  if (manuallyEdited.death) {
    payload.death = metadata.death;
  }
  if (manuallyEdited.special) {
    payload.special = metadata.special;
  }
  if (manuallyEdited.gold_medals) {
    payload.gold_medals = metadata.gold_medals;
  }
  if (manuallyEdited.silver_medals) {
    payload.silver_medals = metadata.silver_medals;
  }
  if (manuallyEdited.allies) {
    payload.allies = [...metadata.allies];
  }
  if (manuallyEdited.enemies) {
    payload.enemies = [...metadata.enemies];
  }

  return payload;
}
