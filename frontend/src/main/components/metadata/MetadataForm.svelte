<script lang="ts">
  import type { MetadataOptionItem } from '../../api/types';

  type WeaponTeam = 'allies' | 'enemies';
  type WeaponSlots = [string, string, string, string];

  export let metadata: {
    match: string;
    rule: string;
    stage: string;
    rate: string;
    judgement: string;
    kill: number;
    death: number;
    special: number;
    allies: WeaponSlots;
    enemies: WeaponSlots;
  };
  export let matchOptions: MetadataOptionItem[] = [];
  export let ruleOptions: MetadataOptionItem[] = [];
  export let stageOptions: MetadataOptionItem[] = [];
  export let judgementOptions: MetadataOptionItem[] = [];

  const placeholderLabel = {
    match: '未取得',
    rule: '未取得',
    stage: '未取得',
    judgement: '未判定',
    rate: '未検出',
  };

  function handleWeaponInput(team: WeaponTeam, index: number, event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const nextSlots = [...metadata[team]] as WeaponSlots;
    nextSlots[index] = input.value;
    metadata = {
      ...metadata,
      [team]: nextSlots,
    };
  }
</script>

<div class="metadata-form">
  <div class="form-group">
    <label for="match">マッチ</label>
    <select id="match" bind:value={metadata.match}>
      <option value="">{placeholderLabel.match}</option>
      {#each matchOptions as match}
        <option value={match.key}>{match.label}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="rule">ルール</label>
    <select id="rule" bind:value={metadata.rule}>
      <option value="">{placeholderLabel.rule}</option>
      {#each ruleOptions as rule}
        <option value={rule.key}>{rule.label}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="stage">ステージ</label>
    <select id="stage" bind:value={metadata.stage}>
      <option value="">{placeholderLabel.stage}</option>
      {#each stageOptions as stage}
        <option value={stage.key}>{stage.label}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="rate">レート</label>
    <input id="rate" type="text" bind:value={metadata.rate} placeholder={placeholderLabel.rate} />
  </div>

  <div class="form-group">
    <label for="judgement">判定</label>
    <select id="judgement" bind:value={metadata.judgement}>
      <option value="">{placeholderLabel.judgement}</option>
      {#each judgementOptions as judgement}
        <option value={judgement.key}>{judgement.label}</option>
      {/each}
    </select>
  </div>

  <div class="stats-grid">
    <div class="form-group">
      <label for="kill">キル数</label>
      <input id="kill" type="number" min="0" bind:value={metadata.kill} />
    </div>

    <div class="form-group">
      <label for="death">デス数</label>
      <input id="death" type="number" min="0" bind:value={metadata.death} />
    </div>

    <div class="form-group">
      <label for="special">スペシャル</label>
      <input id="special" type="number" min="0" bind:value={metadata.special} />
    </div>
  </div>

  <div class="weapon-grid">
    <div class="weapon-team">
      <h3>味方ブキ</h3>
      {#each metadata.allies as weapon, index}
        <div class="form-group">
          <label for={`ally_weapon_${index + 1}`}>味方{index + 1}</label>
          <input
            id={`ally_weapon_${index + 1}`}
            type="text"
            value={weapon}
            placeholder="不明"
            on:input={(event) => handleWeaponInput('allies', index, event)}
          />
        </div>
      {/each}
    </div>

    <div class="weapon-team">
      <h3>敵ブキ</h3>
      {#each metadata.enemies as weapon, index}
        <div class="form-group">
          <label for={`enemy_weapon_${index + 1}`}>敵{index + 1}</label>
          <input
            id={`enemy_weapon_${index + 1}`}
            type="text"
            value={weapon}
            placeholder="不明"
            on:input={(event) => handleWeaponInput('enemies', index, event)}
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
    color: #19d3c7;
    font-size: 0.85rem;
    font-weight: 500;
    text-align: left;
  }

  input,
  select {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
    color: #fff;
    font-size: 0.9rem;
    transition: all 0.2s ease;
  }

  /* selectのドロップダウンリスト */
  select option {
    background: #1a1a2e;
    color: #fff;
    padding: 0.5rem;
  }

  input:focus,
  select:focus {
    outline: none;
    border-color: #19d3c7;
    background: rgba(255, 255, 255, 0.08);
    box-shadow: 0 0 0 3px rgba(25, 211, 199, 0.1);
  }

  input:hover,
  select:hover {
    border-color: rgba(255, 255, 255, 0.25);
  }

  select {
    cursor: pointer;
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
    background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
    background-repeat: no-repeat;
    background-position: right 0.7rem center;
    background-size: 1rem;
    padding-right: 2.5rem;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }

  .stats-grid .form-group {
    min-width: 0;
  }

  .stats-grid input {
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
    color: #19d3c7;
    font-size: 0.9rem;
    font-weight: 600;
    text-align: left;
  }

  @media (max-width: 900px) {
    .weapon-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
