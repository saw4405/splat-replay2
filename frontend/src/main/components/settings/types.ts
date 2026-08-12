export type PrimitiveValue = string | number | boolean | string[];

export type FieldValue = PrimitiveValue | Record<string, PrimitiveValue | Record<string, unknown>>;

export type SettingRequirement = 'required' | 'conditional' | 'optional';

export type SettingDisplayLevel = 'basic' | 'advanced';

export type SettingField = {
  id: string;
  label: string;
  description: string;
  type: string;
  requirement: SettingRequirement;
  requirement_note?: string;
  display_level: SettingDisplayLevel;
  user_editable?: boolean;
  value?: FieldValue | null;
  choices?: string[] | null;
  choice_labels?: Record<string, string> | null;
  children?: SettingField[];
};

export type SettingsSection = {
  id: string;
  label: string;
  fields: SettingField[];
};

export type SettingsResponse = {
  sections: SettingsSection[];
};
