<script lang="ts">
  import type { MetadataOptionItem } from '../../api/types';
  import type { EditableMetadata } from '../../metadata/editable';
  import { normaliseMedalPair, type WeaponSlots } from '../../metadata/shared';

  type WeaponTeam = 'allies' | 'enemies';
  type MedalField = 'goldMedals' | 'silverMedals';
  type FieldLabels = {
    gameMode: string;
    startedAt: string;
    match: string;
    rule: string;
    stage: string;
    rate: string;
    judgement: string;
    kill: string;
    death: string;
    special: string;
    goldMedals: string;
    silverMedals: string;
    allies: string;
    enemies: string;
  };
  type PlaceholderLabels = {
    gameMode: string;
    startedAt: string;
    match: string;
    rule: string;
    stage: string;
    judgement: string;
    rate: string;
  };

  interface Props {
    metadata: EditableMetadata;
    variant?: 'dialog' | 'overlay';
    showGameMode?: boolean;
    gameModeOptions?: MetadataOptionItem[];
    matchOptions?: MetadataOptionItem[];
    ruleOptions?: MetadataOptionItem[];
    stageOptions?: MetadataOptionItem[];
    judgementOptions?: MetadataOptionItem[];
    fieldLabels?: FieldLabels;
    placeholderLabels?: PlaceholderLabels;
    startedAtActionText?: string | null;
    onStartedAtAction?: (() => void) | null;
    onFieldEdited?: ((field: keyof EditableMetadata) => void) | null;
  }

  let {
    metadata = $bindable() as EditableMetadata,
    variant = 'dialog',
    showGameMode = false,
    gameModeOptions = [],
    matchOptions = [],
    ruleOptions = [],
    stageOptions = [],
    judgementOptions = [],
    fieldLabels = {
      gameMode: 'ゲームモード',
      startedAt: '開始時間',
      match: 'マッチ',
      rule: 'ルール',
      stage: 'ステージ',
      rate: 'レート',
      judgement: '判定',
      kill: 'キル数',
      death: 'デス数',
      special: 'スペシャル',
      goldMedals: '金表彰',
      silverMedals: '銀表彰',
      allies: '味方ブキ',
      enemies: '敵ブキ',
    },
    placeholderLabels = {
      gameMode: '未取得',
      startedAt: '例: 2026-03-09 12:34:56',
      match: '未取得',
      rule: '未取得',
      stage: '未取得',
      judgement: '未判定',
      rate: '未検出',
    },
    startedAtActionText = null,
    onStartedAtAction = null,
    onFieldEdited = null,
  }: Props = $props();

  function notifyFieldEdited(field: keyof EditableMetadata): void {
    onFieldEdited?.(field);
  }

  function updateMetadataField<K extends keyof EditableMetadata>(
    field: K,
    value: EditableMetadata[K]
  ): void {
    metadata = {
      ...metadata,
      [field]: value,
    };
    notifyFieldEdited(field);
  }

  function handleTextInput(field: keyof EditableMetadata, event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    updateMetadataField(field, input.value as EditableMetadata[typeof field]);
  }

  function handleSelectChange(field: keyof EditableMetadata, event: Event): void {
    const select = event.currentTarget as HTMLSelectElement;
    updateMetadataField(field, select.value as EditableMetadata[typeof field]);
  }

  function parseNumberInput(value: string): number {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  function handleNumberInput(field: 'kill' | 'death' | 'special', event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    updateMetadataField(field, parseNumberInput(input.value));
  }

  function handleWeaponInput(team: WeaponTeam, index: number, event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const nextSlots = [...metadata[team]] as WeaponSlots;
    nextSlots[index] = input.value;
    updateMetadataField(team, nextSlots);
  }

  function handleMedalInput(field: MedalField, event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const nextMetadata = {
      ...metadata,
      [field]: parseNumberInput(input.value),
    };
    const normalisedMedals = normaliseMedalPair(nextMetadata.goldMedals, nextMetadata.silverMedals);
    metadata = {
      ...nextMetadata,
      goldMedals: normalisedMedals.goldMedals,
      silverMedals: normalisedMedals.silverMedals,
    };
    notifyFieldEdited(field);
  }

  function handleStartedAtAction(): void {
    onStartedAtAction?.();
  }
</script>

<div class="metadata-form" class:variant-overlay={variant === 'overlay'}>
  {#if showGameMode}
    <div class="form-group">
      <label for="game_mode">{fieldLabels.gameMode}</label>
      <select
        id="game_mode"
        value={metadata.gameMode}
        onchange={(event) => handleSelectChange('gameMode', event)}
      >
        <option value="" selected={metadata.gameMode === ''}>{placeholderLabels.gameMode}</option>
        {#each gameModeOptions as mode}
          <option value={mode.key} selected={mode.key === metadata.gameMode}>{mode.label}</option>
        {/each}
      </select>
    </div>
  {/if}

  <div class="form-group">
    <label for="started_at">{fieldLabels.startedAt}</label>
    {#if startedAtActionText}
      <div class="datetime-field">
        <input
          id="started_at"
          type="text"
          value={metadata.startedAt}
          placeholder={placeholderLabels.startedAt}
          oninput={(event) => handleTextInput('startedAt', event)}
        />
        <button type="button" class="started-at-action" onclick={handleStartedAtAction}>
          {startedAtActionText}
        </button>
      </div>
    {:else}
      <input
        id="started_at"
        type="text"
        value={metadata.startedAt}
        placeholder={placeholderLabels.startedAt}
        oninput={(event) => handleTextInput('startedAt', event)}
      />
    {/if}
  </div>

  <div class="form-group">
    <label for="match">{fieldLabels.match}</label>
    <select
      id="match"
      value={metadata.match}
      onchange={(event) => handleSelectChange('match', event)}
    >
      <option value="" selected={metadata.match === ''}>{placeholderLabels.match}</option>
      {#each matchOptions as match}
        <option value={match.key} selected={match.key === metadata.match}>{match.label}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="rule">{fieldLabels.rule}</label>
    <select id="rule" value={metadata.rule} onchange={(event) => handleSelectChange('rule', event)}>
      <option value="" selected={metadata.rule === ''}>{placeholderLabels.rule}</option>
      {#each ruleOptions as rule}
        <option value={rule.key} selected={rule.key === metadata.rule}>{rule.label}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="stage">{fieldLabels.stage}</label>
    <select
      id="stage"
      value={metadata.stage}
      onchange={(event) => handleSelectChange('stage', event)}
    >
      <option value="" selected={metadata.stage === ''}>{placeholderLabels.stage}</option>
      {#each stageOptions as stage}
        <option value={stage.key} selected={stage.key === metadata.stage}>{stage.label}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="rate">{fieldLabels.rate}</label>
    <input
      id="rate"
      type="text"
      value={metadata.rate}
      placeholder={placeholderLabels.rate}
      oninput={(event) => handleTextInput('rate', event)}
    />
  </div>

  <div class="form-group">
    <label for="judgement">{fieldLabels.judgement}</label>
    <select
      id="judgement"
      value={metadata.judgement}
      onchange={(event) => handleSelectChange('judgement', event)}
    >
      <option value="" selected={metadata.judgement === ''}>{placeholderLabels.judgement}</option>
      {#each judgementOptions as judgement}
        <option value={judgement.key} selected={judgement.key === metadata.judgement}>
          {judgement.label}
        </option>
      {/each}
    </select>
  </div>

  <div class="stats-grid">
    <div class="form-group">
      <label for="kill">{fieldLabels.kill}</label>
      <input
        id="kill"
        type="number"
        min="0"
        value={metadata.kill}
        oninput={(event) => handleNumberInput('kill', event)}
      />
    </div>

    <div class="form-group">
      <label for="death">{fieldLabels.death}</label>
      <input
        id="death"
        type="number"
        min="0"
        value={metadata.death}
        oninput={(event) => handleNumberInput('death', event)}
      />
    </div>

    <div class="form-group">
      <label for="special">{fieldLabels.special}</label>
      <input
        id="special"
        type="number"
        min="0"
        value={metadata.special}
        oninput={(event) => handleNumberInput('special', event)}
      />
    </div>
  </div>

  <div class="medals-grid">
    <div class="form-group">
      <label for="gold_medals">{fieldLabels.goldMedals}</label>
      <input
        id="gold_medals"
        type="number"
        min="0"
        max="3"
        value={metadata.goldMedals}
        oninput={(event) => handleMedalInput('goldMedals', event)}
      />
    </div>

    <div class="form-group">
      <label for="silver_medals">{fieldLabels.silverMedals}</label>
      <input
        id="silver_medals"
        type="number"
        min="0"
        max="3"
        value={metadata.silverMedals}
        oninput={(event) => handleMedalInput('silverMedals', event)}
      />
    </div>
  </div>

  <div class="weapon-grid">
    <div class="weapon-team">
      <h3>{fieldLabels.allies}</h3>
      {#each metadata.allies as weapon, index}
        <div class="form-group">
          <label for={`ally_weapon_${index + 1}`}>味方{index + 1}</label>
          <input
            id={`ally_weapon_${index + 1}`}
            type="text"
            value={weapon}
            placeholder="不明"
            oninput={(event) => handleWeaponInput('allies', index, event)}
          />
        </div>
      {/each}
    </div>

    <div class="weapon-team">
      <h3>{fieldLabels.enemies}</h3>
      {#each metadata.enemies as weapon, index}
        <div class="form-group">
          <label for={`enemy_weapon_${index + 1}`}>敵{index + 1}</label>
          <input
            id={`enemy_weapon_${index + 1}`}
            type="text"
            value={weapon}
            placeholder="不明"
            oninput={(event) => handleWeaponInput('enemies', index, event)}
          />
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .metadata-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  label {
    color: var(--accent-color);
    font-size: 0.85rem;
    font-weight: 500;
    text-align: left;
  }

  input,
  select {
    background: rgba(var(--theme-rgb-black), 0.2);
    border: 1px solid rgba(var(--theme-rgb-white), 0.15);
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
    color: var(--theme-color-white);
    font-size: 0.9rem;
    transition: all 0.2s ease;
  }

  /* selectのドロップダウンリスト */
  select option {
    background: var(--theme-panel-navy);
    color: var(--theme-color-white);
    padding: 0.5rem;
  }

  input:focus,
  select:focus {
    outline: none;
    border-color: var(--accent-color);
    background: rgba(var(--theme-rgb-accent), 0.05);
    box-shadow:
      0 0 0 3px rgba(var(--theme-rgb-accent), 0.1),
      inset 0 0 0.5rem rgba(var(--theme-rgb-accent), 0.3);
  }

  input:hover,
  select:hover {
    border-color: rgba(var(--theme-rgb-white), 0.25);
  }

  select {
    cursor: pointer;
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
    background-image:
      linear-gradient(45deg, transparent 50%, var(--theme-color-white) 50%),
      linear-gradient(135deg, var(--theme-color-white) 50%, transparent 50%);
    background-repeat: no-repeat;
    background-position:
      calc(100% - 1rem) calc(50% - 0.1rem),
      calc(100% - 0.7rem) calc(50% - 0.1rem);
    background-size:
      0.35rem 0.35rem,
      0.35rem 0.35rem;
    padding-right: 2.5rem;
  }

  .datetime-field {
    display: flex;
    gap: 0.5rem;
  }

  .datetime-field input {
    flex: 1;
  }

  .started-at-action {
    padding: 0.5rem 1rem;
    border: 1px solid rgba(var(--theme-rgb-white), 0.2);
    border-radius: 999px;
    background: rgba(var(--theme-rgb-white), 0.08);
    color: var(--theme-color-white);
    font-size: 0.8125rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
  }

  .started-at-action:hover {
    background: rgba(var(--theme-rgb-white), 0.14);
    border-color: rgba(var(--theme-rgb-white), 0.28);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }

  .medals-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .stats-grid .form-group {
    min-width: 0;
  }

  .stats-grid input,
  .medals-grid input {
    width: 100%;
    box-sizing: border-box;
  }

  .weapon-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .weapon-team {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .weapon-team h3 {
    margin: 0;
    color: var(--theme-accent-color);
    font-size: 0.9rem;
    font-weight: 600;
    text-align: left;
  }

  @media (max-width: 900px) {
    .weapon-grid {
      grid-template-columns: 1fr;
    }
  }

  .variant-overlay .form-group label {
    font-size: 0.8125rem;
    letter-spacing: 0.02em;
  }

  .variant-overlay input,
  .variant-overlay select {
    padding: 0.55rem 0.85rem;
    border-radius: calc(var(--glass-radius) - 8px);
    border: 1px solid rgba(var(--theme-rgb-white), 0.14);
    background: rgba(var(--theme-rgb-black), 0.2);
    color: var(--text-primary);
    font-size: 0.875rem;
    box-shadow:
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.06),
      0 1px 12px rgba(var(--theme-rgb-black), 0.25);
  }

  .variant-overlay select {
    background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='rgba(var(--theme-rgb-white), 0.7)' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
    background-size: 1rem;
  }

  .variant-overlay input:focus,
  .variant-overlay select:focus {
    border-color: rgba(var(--theme-rgb-accent), 0.55);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.22) 0%,
      rgba(var(--theme-rgb-accent), 0.08) 100%
    );
    box-shadow:
      0 0 0 2px rgba(var(--theme-rgb-ring-strong), 0.75),
      0 0 0 4px rgba(var(--theme-rgb-accent), 0.2),
      0 12px 24px rgba(var(--theme-rgb-accent), 0.18),
      inset 0 0 0.5rem rgba(var(--theme-rgb-accent), 0.3);
  }

  .variant-overlay input:hover,
  .variant-overlay select:hover {
    border-color: rgba(var(--theme-rgb-white), 0.22);
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-white), 0.12) 0%,
      rgba(var(--theme-rgb-white), 0.06) 100%
    );
  }

  .variant-overlay input::placeholder {
    color: rgba(var(--theme-rgb-white), 0.45);
  }

  .variant-overlay .stats-grid {
    gap: 0.5rem;
  }

  .variant-overlay .stats-grid input {
    text-align: center;
  }

  .variant-overlay .weapon-grid {
    gap: 0.75rem;
  }

  .variant-overlay .weapon-team {
    gap: 0.5rem;
    padding: 0.65rem;
    border: 1px solid rgba(var(--theme-rgb-accent), 0.2);
    border-radius: calc(var(--glass-radius) - 8px);
    background: rgba(var(--theme-rgb-surface-card-dark), 0.4);
  }

  .variant-overlay .weapon-team h3 {
    font-size: 0.78rem;
    letter-spacing: 0.04em;
    color: var(--accent-color);
  }

  .variant-overlay .started-at-action {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.24) 0%,
      rgba(var(--theme-rgb-accent), 0.14) 100%
    );
    border-color: rgba(var(--theme-rgb-accent), 0.45);
    color: var(--accent-color);
    box-shadow:
      0 6px 18px rgba(var(--theme-rgb-accent), 0.2),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.18);
  }

  .variant-overlay .started-at-action:hover {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.38) 0%,
      rgba(var(--theme-rgb-accent), 0.24) 100%
    );
    border-color: rgba(var(--theme-rgb-accent), 0.6);
    box-shadow:
      0 6px 18px rgba(var(--theme-rgb-accent), 0.28),
      0 0 20px rgba(var(--theme-rgb-accent), 0.2),
      inset 0 1px 0 rgba(var(--theme-rgb-white), 0.2);
  }

  @media (max-width: 640px) {
    .stats-grid,
    .medals-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
