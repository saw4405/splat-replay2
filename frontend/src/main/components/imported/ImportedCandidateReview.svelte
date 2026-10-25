<script lang="ts">
  import ImportedEvidencePanel from './ImportedEvidencePanel.svelte';
  import type { ImportedBattle } from '../../api/importedVideos';
  import { importedAssetUrl } from '../../api/importedVideos';
  import type { MetadataOptions } from '../../api/types';

  type MetadataValue = string | number | string[] | null;
  interface Props {
    jobId: string;
    candidate: ImportedBattle;
    options: MetadataOptions | null;
    patch: Record<string, MetadataValue>;
    disabled: boolean;
    displayedPanel?: 'match_select' | 'weapons' | 'result_full' | 'judgement';
    onChange: (key: string, value: MetadataValue) => void;
  }
  let { jobId, candidate, options, patch, disabled, displayedPanel, onChange }: Props = $props();
  const panels = [
    {
      key: 'match_select',
      title: 'マッチ選択画面',
      size: [1920, 1080] as [number, number],
      width: '0',
      fields: [
        { key: 'match', label: 'マッチ', options: 'matches' },
        { key: 'rate', label: 'レート' },
      ],
    },
    {
      key: 'weapons',
      title: 'バトル中のイカランプ',
      size: [920, 120] as [number, number],
      width: '50rem',
      fields: ['allies', 'enemies'].flatMap((team) =>
        [0, 1, 2, 3].map((index) => ({
          key: `${team}_${index}`,
          label: `${team === 'allies' ? '味方' : '相手'}${index + 1}`,
        }))
      ),
    },
    {
      key: 'result_full',
      title: 'リザルト画面',
      size: [1920, 1080] as [number, number],
      width: '0',
      fields: [
        { key: 'rule', label: 'ルール', options: 'rules' },
        { key: 'stage', label: 'ステージ', options: 'stages' },
        { key: 'kill', label: 'キル' },
        { key: 'death', label: 'デス' },
        { key: 'special', label: 'スペシャル' },
        { key: 'gold_medals', label: '金表彰' },
        { key: 'silver_medals', label: '銀表彰' },
      ],
    },
    {
      key: 'judgement',
      title: 'ジャッジ画面',
      size: [340, 200] as [number, number],
      width: '0',
      fields: [{ key: 'judgement', label: 'ジャッジ', options: 'judgements' }],
    },
  ];
  let judgementWidth = $derived(
    `calc(max(50rem, 100cqw - 0.5rem) * ${candidate.evidence_sizes?.judgement?.[0] ?? 340} / ${candidate.evidence_sizes?.weapons?.[0] ?? 920})`
  );
  const selects: Record<string, 'matches' | 'rules' | 'stages' | 'judgements'> = {
    match: 'matches',
    rule: 'rules',
    stage: 'stages',
    judgement: 'judgements',
  };
  const fieldLabels: Record<string, string> = {
    match: 'マッチ',
    rate: 'レート',
    rule: 'ルール',
    stage: 'ステージ',
    kill: 'キル',
    death: 'デス',
    special: 'スペシャル',
    gold_medals: '金表彰',
    silver_medals: '銀表彰',
    judgement: 'ジャッジ',
  };
  function value(key: string): ImportedBattle['metadata'][string] {
    return key in patch ? patch[key] : candidate.metadata[key];
  }
  function text(key: string): string {
    const current = value(key);
    return typeof current === 'string' || typeof current === 'number' ? String(current) : '';
  }
  function weapons(team: 'allies' | 'enemies'): string[] {
    const current = value(team);
    return [0, 1, 2, 3].map((index) =>
      Array.isArray(current) ? String(current[index] ?? '') : ''
    );
  }
  function changeWeapon(team: 'allies' | 'enemies', index: number, name: string): void {
    const names = weapons(team);
    names[index] = name;
    onChange(team, names);
  }
  function crop(kind: string): [number, number] | undefined {
    const regions = candidate.evidence_regions?.[kind];
    const height = candidate.evidence_sizes?.[kind]?.[1] ?? 1080;
    if (kind === 'match_select') {
      const areas = [regions?.match, regions?.rate].filter(
        (region): region is [number, number, number, number] => region !== undefined
      );
      if (areas.length) {
        // 色検出点だけではマッチ名を読めないため、名前とレートの表示文脈を含める。
        return [
          Math.max(0, Math.min((height * 190) / 1080, ...areas.map((region) => region[1]))),
          Math.min(
            height,
            Math.max((height * 600) / 1080, ...areas.map((region) => region[1] + region[3]))
          ),
        ];
      }
    }
    if (kind === 'result_full') {
      const medals = regions?.gold_medals ?? regions?.silver_medals;
      if (medals) return [0, Math.min(height, medals[1] + medals[3])];
    }
    return undefined;
  }
  function evidence(kind: string): string | undefined {
    return candidate.evidence_assets?.[kind];
  }
</script>

<div class="quality-review">
  {#if !displayedPanel || displayedPanel === 'match_select'}
    <div class="basic-fields">
      <div class="mode-field">
        モード <span class="readonly"
          >{options?.gameModes?.find((item) => item.key === candidate.metadata.game_mode)?.label ??
            candidate.metadata.game_mode ??
            '未取得'}</span
        >
      </div>
      <label
        >開始日時<input
          aria-label="開始日時"
          type="datetime-local"
          step="1"
          {disabled}
          value={text('started_at').replace(' ', 'T').slice(0, 19)}
          oninput={(event) => onChange('started_at', event.currentTarget.value || null)}
        /></label
      >
    </div>
  {/if}
  {#each panels.filter((panel) => !displayedPanel || panel.key === displayedPanel) as panel}
    <ImportedEvidencePanel
      title={panel.title}
      imageUrl={evidence(panel.key) ? importedAssetUrl(jobId, evidence(panel.key)!) : undefined}
      imageSize={candidate.evidence_sizes?.[panel.key] ?? panel.size}
      regions={candidate.evidence_regions?.[panel.key]}
      fields={panel.fields}
      crop={crop(panel.key)}
      topFieldKeys={panel.key === 'result_full'
        ? ['rule', 'stage', 'kill', 'death', 'special']
        : []}
      seconds={candidate.evidence_seconds?.[panel.key]}
      minWidth={panel.key === 'judgement' ? judgementWidth : panel.width}
      maxWidth={panel.key === 'judgement'
        ? judgementWidth
        : panel.key === 'result_full'
          ? 'min(100%, 50rem)'
          : '100%'}
    >
      {#snippet children(key)}
        {#if key.startsWith('allies_') || key.startsWith('enemies_')}
          {@const team = key.startsWith('allies_') ? 'allies' : 'enemies'}
          {@const index = Number(key.split('_')[1])}
          <div class="weapon-select">
            <span aria-hidden="true"
              >{options?.weapons?.find((option) => option.key === weapons(team)[index])?.label ??
                (weapons(team)[index] || '未取得')}</span
            >
            <span class="select-arrow" aria-hidden="true">▾</span>
            <select
              aria-label={`${team === 'allies' ? '味方' : '相手'}${index + 1}のブキ`}
              {disabled}
              value={weapons(team)[index]}
              onchange={(event) => changeWeapon(team, index, event.currentTarget.value)}
            >
              <option value="">未取得</option>
              {#if weapons(team)[index] && !options?.weapons?.some((option) => option.key === weapons(team)[index])}
                <option value={weapons(team)[index]}>{weapons(team)[index]}</option>
              {/if}
              {#each options?.weapons ?? [] as option}
                <option value={option.key}>{option.label}</option>
              {/each}
            </select>
          </div>
        {:else if selects[key]}
          <select
            aria-label={fieldLabels[key]}
            {disabled}
            value={text(key)}
            onchange={(event) => onChange(key, event.currentTarget.value || null)}
          >
            <option value="">未取得</option>
            {#if text(key) && !options?.[selects[key]]?.some((option) => option.key === text(key))}<option
                value={text(key)}>{text(key)}</option
              >{/if}
            {#each options?.[selects[key]] ?? [] as option}<option value={option.key}
                >{option.label}</option
              >{/each}
          </select>
        {:else if key === 'rate'}
          <input
            aria-label="レート"
            {disabled}
            placeholder="未取得"
            value={text(key)}
            oninput={(event) => onChange(key, event.currentTarget.value || null)}
          />
        {:else}
          <input
            aria-label={fieldLabels[key]}
            type="number"
            min="0"
            max={key.endsWith('medals') ? 3 : undefined}
            {disabled}
            placeholder="未取得"
            value={text(key)}
            oninput={(event) =>
              onChange(
                key,
                event.currentTarget.value === '' ? null : Number(event.currentTarget.value)
              )}
          />
        {/if}
      {/snippet}
    </ImportedEvidencePanel>
  {/each}
</div>

<style>
  .quality-review {
    container-type: inline-size;
    display: grid;
    gap: 1rem;
    text-align: left;
    min-width: 0;
  }
  .basic-fields {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
    gap: 0.75rem;
  }
  label,
  .mode-field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.75rem;
    min-width: 0;
  }
  .weapon-select {
    position: relative;
    display: flex;
    align-items: center;
    min-height: 4.25rem;
    box-sizing: border-box;
    border: 1px solid var(--glass-border);
    border-radius: 0.4rem;
    background: rgba(var(--theme-rgb-black), 0.2);
    padding: 0.4rem 1rem 0.4rem 0.4rem;
    font-size: 0.8rem;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }
  .weapon-select select {
    position: absolute;
    inset: 0;
    height: 100%;
    opacity: 0;
    cursor: pointer;
  }
  .weapon-select:focus-within {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 1px;
  }
  .select-arrow {
    position: absolute;
    right: 0.35rem;
  }
  input,
  select,
  .readonly {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
    border: 1px solid var(--glass-border);
    border-radius: 0.4rem;
    background: rgba(var(--theme-rgb-black), 0.2);
    color: var(--theme-color-text-primary);
    font: inherit;
    font-size: 0.8rem;
    padding: 0.4rem;
  }
  input,
  select {
    height: 2.25rem;
  }
  .readonly {
    border-color: transparent;
  }
  input:focus-visible,
  select:focus-visible {
    outline: 2px solid var(--theme-accent-color);
    outline-offset: 1px;
  }
</style>
