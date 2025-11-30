export type PrimitiveValue = string | number | boolean | string[];

export type FieldValue = PrimitiveValue | Record<string, FieldValue>;

export type SettingField = {
  id: string;
  label: string;
  description: string;
  type: string;
  recommended: boolean;
  value?: FieldValue | null;
  choices?: string[] | null;
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
