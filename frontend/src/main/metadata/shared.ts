export type WeaponSlots = [string, string, string, string];

type MedalCounts = {
  goldMedals: number;
  silverMedals: number;
};

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

export function normaliseMedalCount(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(3, Math.max(0, Math.trunc(value)));
}

export function normaliseMedalPair(goldMedals: number, silverMedals: number): MedalCounts {
  const nextGold = normaliseMedalCount(goldMedals);
  const nextSilver = Math.min(normaliseMedalCount(silverMedals), 3 - nextGold);
  return {
    goldMedals: nextGold,
    silverMedals: nextSilver,
  };
}

export function formatMetadataDateTime(value: string | null | undefined): string {
  if (!value) {
    return '';
  }

  const trimmed = value.trim();
  if (trimmed === '') {
    return '';
  }

  const isoLikeMatch = trimmed.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  if (isoLikeMatch) {
    return `${isoLikeMatch[1]} ${isoLikeMatch[2]}`;
  }

  return trimmed;
}
