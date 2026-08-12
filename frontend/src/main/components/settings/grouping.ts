import type { FieldValue, PrimitiveValue, SettingField, SettingsSection } from './types';

export type SettingsDisplayMode = 'basic' | 'all';

export type SettingsUpdateSection = {
  id: string;
  values: Record<string, FieldValue>;
};

export type SettingsUiField = SettingField & {
  sourceSectionId: string;
};

export type SettingsUiSection = Omit<SettingsSection, 'fields'> & {
  fields: SettingsUiField[];
  sourceSectionIds: string[];
};

type SettingsGroupDefinition = {
  id: string;
  label: string;
  sourceSectionIds: string[];
  layout: 'flat' | 'sectioned';
};

const SETTINGS_GROUPS: SettingsGroupDefinition[] = [
  { id: 'behavior', label: '動作', sourceSectionIds: ['behavior'], layout: 'flat' },
  {
    id: 'display',
    label: '表示',
    sourceSectionIds: ['webview', 'remote_access'],
    layout: 'flat',
  },
  {
    id: 'recording',
    label: '録画',
    sourceSectionIds: ['capture_device', 'obs', 'record', 'speech_transcriber'],
    layout: 'sectioned',
  },
  { id: 'edit', label: '編集', sourceSectionIds: ['video_edit'], layout: 'flat' },
  { id: 'upload', label: 'アップロード', sourceSectionIds: ['upload'], layout: 'flat' },
];

const SOURCE_SECTION_LABELS: Record<string, string> = {
  webview: '表示',
  remote_access: 'LAN 公開',
  capture_device: 'キャプチャデバイス',
  obs: 'OBS接続',
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

export function filterSettingsFieldsByDisplayMode(
  fields: SettingsUiField[],
  mode: SettingsDisplayMode
): SettingsUiField[] {
  if (mode === 'all') {
    return fields;
  }

  const visibleFields: SettingsUiField[] = [];

  for (const field of fields) {
    if (field.type === 'group' && field.children) {
      const visibleChildren = filterBasicSettingFields(field.children);
      if (visibleChildren.length > 0) {
        visibleFields.push({
          ...field,
          children: visibleChildren,
        });
      }
      continue;
    }

    if (field.display_level === 'basic') {
      visibleFields.push(field);
    }
  }

  return visibleFields;
}

export function filterSettingsSectionsByDisplayMode(
  sections: SettingsUiSection[],
  mode: SettingsDisplayMode
): SettingsUiSection[] {
  if (mode === 'all') {
    return sections;
  }

  return sections.flatMap((section) => {
    const fields = filterSettingsFieldsByDisplayMode(section.fields, mode);
    if (fields.length === 0) {
      return [];
    }
    return [{ ...section, fields }];
  });
}

function filterBasicSettingFields(fields: SettingField[]): SettingField[] {
  const visibleFields: SettingField[] = [];

  for (const field of fields) {
    if (field.type === 'group' && field.children) {
      const visibleChildren = filterBasicSettingFields(field.children);
      if (visibleChildren.length > 0) {
        visibleFields.push({
          ...field,
          children: visibleChildren,
        });
      }
      continue;
    }

    if (field.display_level === 'basic') {
      visibleFields.push(field);
    }
  }

  return visibleFields;
}

function filterEditableSections(sectionsData: SettingsSection[]): SettingsUiSection[] {
  return sectionsData
    .map((section) => {
      const fields = filterEditableFields(section.fields).map((field) => ({
        ...field,
        sourceSectionId: section.id,
      }));
      return {
        ...section,
        fields,
        sourceSectionIds: [section.id],
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
    if (group.layout === 'sectioned') {
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
          requirement: 'optional',
          display_level: 'advanced',
          user_editable: true,
          children,
          value: collectGroupValues(children),
        };
        return [{ ...groupField, sourceSectionId }];
      });

      if (fields.length > 0) {
        groupedSections.push({
          id: group.id,
          label: group.label,
          fields,
          sourceSectionIds: group.sourceSectionIds,
        });
      }
      continue;
    }

    const fields = group.sourceSectionIds.flatMap((sourceSectionId) => {
      const sourceSection = sectionsById.get(sourceSectionId);
      if (!sourceSection) {
        return [];
      }
      return filterEditableFields(sourceSection.fields).map((field) => ({
        ...field,
        sourceSectionId,
      }));
    });
    if (fields.length === 0) {
      continue;
    }

    groupedSections.push({
      id: group.id,
      label: group.label,
      fields,
      sourceSectionIds: group.sourceSectionIds,
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
    const valuesBySourceSection = new Map<string, Record<string, FieldValue>>();

    for (const field of section.fields) {
      const values = valuesBySourceSection.get(field.sourceSectionId) ?? {};
      if (field.type === 'group' && field.children) {
        Object.assign(values, collectGroupValues(field.children));
      } else {
        values[field.id] = collectFieldValue(field);
      }
      valuesBySourceSection.set(field.sourceSectionId, values);
    }

    for (const sourceSectionId of section.sourceSectionIds) {
      const values = valuesBySourceSection.get(sourceSectionId);
      if (!values) {
        continue;
      }
      updates.push({
        id: sourceSectionId,
        values,
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
