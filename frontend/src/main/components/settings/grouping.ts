import type { FieldValue, PrimitiveValue, SettingField, SettingsSection } from './types';

export type SettingsUpdateSection = {
  id: string;
  values: Record<string, FieldValue>;
};

export type SettingsUiSection = SettingsSection & {
  sourceSectionIds: string[];
  grouped: boolean;
};

type SettingsGroupDefinition = {
  id: string;
  label: string;
  sourceSectionIds: string[];
  grouped: boolean;
};

const SETTINGS_GROUPS: SettingsGroupDefinition[] = [
  { id: 'behavior', label: '動作', sourceSectionIds: ['behavior'], grouped: false },
  { id: 'display', label: '表示', sourceSectionIds: ['webview'], grouped: false },
  {
    id: 'recording',
    label: '録画',
    sourceSectionIds: ['capture_device', 'obs', 'record', 'speech_transcriber'],
    grouped: true,
  },
  { id: 'edit', label: '編集', sourceSectionIds: ['video_edit'], grouped: false },
  { id: 'upload', label: 'アップロード', sourceSectionIds: ['upload'], grouped: false },
];

const SOURCE_SECTION_LABELS: Record<string, string> = {
  capture_device: 'キャプチャデバイス',
  obs: 'OBS 接続',
  record: '録画',
  speech_transcriber: '文字起こし',
};

export function cloneSettingField(field: SettingField): SettingField {
  return {
    ...field,
    children: field.children?.map(cloneSettingField),
  };
}

export function filterEditableFields(fields: SettingField[]): SettingField[] {
  const result: SettingField[] = [];

  for (const field of fields) {
    if (field.type === 'group' && field.children) {
      const children = filterEditableFields(field.children);
      if (children.length > 0) {
        result.push({
          ...cloneSettingField(field),
          children,
        });
      }
      continue;
    }

    if (field.user_editable) {
      result.push(cloneSettingField(field));
    }
  }

  return result;
}

function filterEditableSections(sectionsData: SettingsSection[]): SettingsUiSection[] {
  return sectionsData
    .map((section) => {
      const fields = filterEditableFields(section.fields);
      return {
        ...section,
        fields,
        sourceSectionIds: [section.id],
        grouped: false,
      };
    })
    .filter((section) => section.fields.length > 0);
}

export function groupSettingsSections(sourceSections: SettingsSection[]): SettingsUiSection[] {
  const sectionsById = new Map(sourceSections.map((section) => [section.id, section]));
  const hasKnownSection = SETTINGS_GROUPS.some((group) =>
    group.sourceSectionIds.some((sourceSectionId) => sectionsById.has(sourceSectionId))
  );

  if (!hasKnownSection) {
    return filterEditableSections(sourceSections);
  }

  const groupedSections: SettingsUiSection[] = [];

  for (const group of SETTINGS_GROUPS) {
    if (group.grouped) {
      const fields = group.sourceSectionIds.flatMap((sourceSectionId) => {
        const sourceSection = sectionsById.get(sourceSectionId);
        if (!sourceSection) {
          return [];
        }

        const children = filterEditableFields(sourceSection.fields);
        if (children.length === 0) {
          return [];
        }

        const groupField: SettingField = {
          id: sourceSectionId,
          label: SOURCE_SECTION_LABELS[sourceSectionId] ?? sourceSection.label,
          description: '',
          type: 'group',
          recommended: false,
          user_editable: true,
          children,
          value: collectGroupValues(children),
        };
        return [groupField];
      });

      if (fields.length > 0) {
        groupedSections.push({
          id: group.id,
          label: group.label,
          fields,
          sourceSectionIds: group.sourceSectionIds,
          grouped: true,
        });
      }
      continue;
    }

    const sourceSectionId = group.sourceSectionIds[0];
    const sourceSection = sectionsById.get(sourceSectionId);
    if (!sourceSection) {
      continue;
    }

    const fields = filterEditableFields(sourceSection.fields);
    if (fields.length === 0) {
      continue;
    }

    groupedSections.push({
      id: group.id,
      label: group.label,
      fields,
      sourceSectionIds: [sourceSectionId],
      grouped: false,
    });
  }

  return groupedSections;
}

export function collectSectionValues(section: SettingsSection): Record<string, FieldValue> {
  const values: Record<string, FieldValue> = {};
  for (const field of section.fields) {
    values[field.id] = collectFieldValue(field);
  }
  return values;
}

export function collectFieldValue(field: SettingField): FieldValue {
  if (field.type === 'group' && field.children) {
    return collectGroupValues(field.children);
  }
  if (field.type === 'list') {
    return Array.isArray(field.value) ? field.value : [];
  }
  if (typeof field.value === 'undefined' || field.value === null) {
    if (field.type === 'boolean') {
      return false;
    }
    if (field.type === 'integer' || field.type === 'float') {
      return 0;
    }
    return '';
  }
  return field.value;
}

export function collectGroupValues(fields: SettingField[]): Record<string, PrimitiveValue> {
  const result: Record<string, PrimitiveValue> = {};
  for (const child of fields) {
    const value = collectFieldValue(child);
    if (isPrimitiveValue(value)) {
      result[child.id] = value;
    }
  }
  return result;
}

export function collectSettingsUpdateSections(
  sections: SettingsUiSection[]
): SettingsUpdateSection[] {
  const updates: SettingsUpdateSection[] = [];

  for (const section of sections) {
    if (!section.grouped) {
      const sourceSectionId = section.sourceSectionIds[0] ?? section.id;
      updates.push({
        id: sourceSectionId,
        values: collectSectionValues(section),
      });
      continue;
    }

    for (const sourceSectionId of section.sourceSectionIds) {
      const sourceField = section.fields.find((field) => field.id === sourceSectionId);
      if (!sourceField || sourceField.type !== 'group' || !sourceField.children) {
        continue;
      }
      updates.push({
        id: sourceSectionId,
        values: collectGroupValues(sourceField.children),
      });
    }
  }

  return updates;
}

function isPrimitiveValue(value: FieldValue): value is PrimitiveValue {
  return (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean' ||
    (Array.isArray(value) && value.every((item) => typeof item === 'string'))
  );
}
