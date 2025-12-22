<script lang="ts">
  export let metadata: {
    match: string;
    rule: string;
    stage: string;
    rate: string;
    judgement: string;
    kill: number;
    death: number;
    special: number;
  };

  const matches = [
    '未取得',
    'レギュラーマッチ',
    'バンカラマッチ(チャレンジ)',
    'バンカラマッチ(オープン)',
    'Xマッチ',
    'イベントマッチ',
    'プライベートマッチ',
  ];

  const rules = [
    '未取得',
    'ナワバリ',
    'ガチエリア',
    'ガチヤグラ',
    'ガチホコ',
    'ガチアサリ',
    'トリカラ',
  ];

  const judgements = ['未判定', 'WIN', 'LOSE'];
</script>

<div class="metadata-form">
  <div class="form-group">
    <label for="match">マッチ</label>
    <select id="match" bind:value={metadata.match}>
      {#each matches as match}
        <option value={match}>{match}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="rule">ルール</label>
    <select id="rule" bind:value={metadata.rule}>
      {#each rules as rule}
        <option value={rule}>{rule}</option>
      {/each}
    </select>
  </div>

  <div class="form-group">
    <label for="stage">ステージ</label>
    <input id="stage" type="text" bind:value={metadata.stage} />
  </div>

  <div class="form-group">
    <label for="rate">レート</label>
    <input id="rate" type="text" bind:value={metadata.rate} />
  </div>

  <div class="form-group">
    <label for="judgement">判定</label>
    <select id="judgement" bind:value={metadata.judgement}>
      {#each judgements as judgement}
        <option value={judgement}>{judgement}</option>
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
    /* WebKitブラウザでのデフォルトスタイルを上書き */
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
</style>
