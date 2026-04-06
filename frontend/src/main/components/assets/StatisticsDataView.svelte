<script lang="ts">
  import type { BattleHistoryEntry } from '../../api/types';

  export let battles: BattleHistoryEntry[] = [];

  // ---- 日本語マッピング ----
  const RULE_LABELS: Record<string, string> = {
    TURF_WAR: 'ナワバリバトル',
    SPLAT_ZONES: 'ガチエリア',
    TOWER_CONTROL: 'ガチヤグラ',
    RAINMAKER: 'ガチホコ',
    CLAM_BLITZ: 'ガチアサリ',
    TRICOLOR_TURF_WAR: 'トリカラバトル',
  };

  const STAGE_LABELS: Record<string, string> = {
    SCORCH_GORGE: 'ユノハナ大渓谷',
    EELTAIL_ALLEY: 'ゴンズイ地区',
    HAGGLEFISH_MARKET: 'ヤガラ市場',
    UNDERTOW_SPILLWAY: 'マテガイ放水路',
    MINCEMEAT_METALWORKS: 'ナメロウ金属',
    MAHI_MAHI_RESORT: 'マヒマヒリゾート＆スパ',
    MUSEUM_D_ALFONSINO: 'キンメダイ美術館',
    HAMMERHEAD_BRIDGE: 'マサバ海峡大橋',
    INKBLOT_ART_ACADEMY: '海女美術大学',
    STURGEON_SHIPYARD: 'チョウザメ造船',
    MAKO_MART: 'ザトウマーケット',
    WAHOO_WORLD: 'スメーシーワールド',
    FLOUNDER_HEIGHTS: 'ヒラメが丘団地',
    BRINEWATER_SPRINGS: 'クサヤ温泉',
    UMAMI_RUINS: 'ナンプラー遺跡',
    MANTA_MARIA: 'マンタマリア号',
    BARNACLE_AND_DIME: 'タラポートショッピングパーク',
    HUMPBACK_PUMP_TRACK: 'コンブトラック',
    CRABLEG_CAPITAL: 'タカアシ経済特区',
    SHIPSHAPE_CARGO_CO: 'オヒョウ海運',
    ROBO_ROM_EN: 'バイガイ亭',
    BLUEFIN_DEPOT: 'ネギトロ炭鉱',
    MARLIN_AIRPORT: 'カジキ空港',
    LEMURIA_HUB: 'リュウグウターミナル',
    URCHIN_UNDERPASS: 'デカライン高架下',
  };

  function ruleLabel(key: string | null): string {
    if (!key) return '不明';
    return RULE_LABELS[key] ?? key;
  }

  function stageLabel(key: string | null): string {
    if (!key) return '不明';
    return STAGE_LABELS[key] ?? key;
  }

  function isWin(judgement: string | null): boolean {
    const j = judgement?.toLowerCase();
    return j === 'win' || j === 'victory' || j === '勝利';
  }

  function isLoss(judgement: string | null): boolean {
    const j = judgement?.toLowerCase();
    return j === 'lose' || j === 'defeat' || j === '敗北';
  }

  // バトルデータのみ対象
  $: battleVideos = battles.filter(
    (v) => v.kill !== null || v.death !== null || v.judgement !== null
  );

  // 総合
  $: totalMatches = battleVideos.length;
  $: wins = battleVideos.filter((v) => isWin(v.judgement)).length;
  $: losses = battleVideos.filter((v) => isLoss(v.judgement)).length;
  $: validDecisions = wins + losses;
  $: winRate = validDecisions > 0 ? (wins / validDecisions) * 100 : 0;

  $: totalKills = battleVideos.reduce((acc, v) => acc + (v.kill ?? 0), 0);
  $: totalDeaths = battleVideos.reduce((acc, v) => acc + (v.death ?? 0), 0);
  $: totalSpecials = battleVideos.reduce((acc, v) => acc + (v.special ?? 0), 0);
  $: avgKills = totalMatches > 0 ? totalKills / totalMatches : 0;
  $: avgDeaths = totalMatches > 0 ? totalDeaths / totalMatches : 0;
  $: avgSpecials = totalMatches > 0 ? totalSpecials / totalMatches : 0;
  $: kdRatio = totalDeaths > 0 ? totalKills / totalDeaths : totalKills;

  // ルール別→ステージ別集計
  type StageRecord = { matches: number; wins: number; losses: number };
  type RuleRecord = {
    matches: number;
    wins: number;
    losses: number;
    stages: Record<string, StageRecord>;
  };

  $: ruleStats = battleVideos.reduce(
    (acc, v) => {
      const rKey = v.rule ?? '不明';
      if (!acc[rKey]) acc[rKey] = { matches: 0, wins: 0, losses: 0, stages: {} };
      acc[rKey].matches += 1;
      if (isWin(v.judgement)) acc[rKey].wins += 1;
      if (isLoss(v.judgement)) acc[rKey].losses += 1;

      const sKey = v.stage ?? '不明';
      if (!acc[rKey].stages[sKey]) acc[rKey].stages[sKey] = { matches: 0, wins: 0, losses: 0 };
      acc[rKey].stages[sKey].matches += 1;
      if (isWin(v.judgement)) acc[rKey].stages[sKey].wins += 1;
      if (isLoss(v.judgement)) acc[rKey].stages[sKey].losses += 1;

      return acc;
    },
    {} as Record<string, RuleRecord>
  );

  $: ruleEntries = Object.entries(ruleStats).sort((a, b) => b[1].matches - a[1].matches);

  // 展開状態（ルールのキーをセットで管理）
  let expanded = new Set<string>();
  function toggle(key: string) {
    if (expanded.has(key)) {
      expanded.delete(key);
    } else {
      expanded.add(key);
    }
    expanded = new Set(expanded); // reactivity trigger
  }
</script>

<div class="statistics-container">
  {#if totalMatches === 0}
    <div class="empty-state glass-panel">
      <div class="empty-icon">📊</div>
      <p>戦績データがありません</p>
    </div>
  {:else}
    <div class="stat-grid">
      <!-- 総合サマリー -->
      <div class="stat-card primary">
        <h4 class="card-title">総試合数</h4>
        <div class="card-value">{totalMatches} <span class="unit">戦</span></div>
        <div class="card-sub">{wins}勝 {losses}敗</div>
      </div>

      <div class="stat-card">
        <h4 class="card-title">勝率</h4>
        <div class="card-value {winRate >= 50 ? 'positive' : 'negative'}">
          {winRate.toFixed(1)}<span class="unit">%</span>
        </div>
      </div>

      <div class="stat-card">
        <h4 class="card-title">平均キル / デス</h4>
        <div class="card-value combo">
          <span class="kill">{avgKills.toFixed(1)}</span>
          <span class="separator">/</span>
          <span class="death">{avgDeaths.toFixed(1)}</span>
        </div>
        <div class="card-sub">K/D: {kdRatio.toFixed(2)}</div>
      </div>

      <div class="stat-card">
        <h4 class="card-title">平均スペシャル</h4>
        <div class="card-value special">{avgSpecials.toFixed(1)} <span class="unit">回</span></div>
      </div>
    </div>

    <!-- ルール別→ステージ別 -->
    <div class="detail-card">
      <h4 class="detail-title">ルール別勝率</h4>
      <div class="scroll-list">
        <ul class="rule-list">
          {#each ruleEntries as [rKey, rStat]}
            {@const rWinRate =
              rStat.wins + (rStat.matches - rStat.wins) > 0
                ? (rStat.wins / rStat.matches) * 100
                : 0}
            <li class="rule-row">
              <button
                class="rule-header"
                onclick={() => toggle(rKey)}
                aria-expanded={expanded.has(rKey)}
              >
                <span class="chevron" class:open={expanded.has(rKey)}>›</span>
                <span class="rule-name">{ruleLabel(rKey)}</span>
                <span class="rule-meta">
                  <span class="count">{rStat.matches}戦</span>
                  <span class="count">{rStat.wins}勝{rStat.losses}敗</span>
                  <span
                    class="win-rate-badge"
                    class:positive={rWinRate >= 50}
                    class:negative={rWinRate < 50}
                  >
                    {rWinRate.toFixed(1)}%
                  </span>
                </span>
              </button>

              {#if expanded.has(rKey)}
                <ul class="stage-list">
                  {#each Object.entries(rStat.stages).sort((a, b) => b[1].matches - a[1].matches) as [sKey, sStat]}
                    {@const sWinRate = sStat.matches > 0 ? (sStat.wins / sStat.matches) * 100 : 0}
                    <li class="stage-row">
                      <span class="stage-name">{stageLabel(sKey)}</span>
                      <span class="stage-meta">
                        <span class="count">{sStat.matches}戦</span>
                        <span class="count">{sStat.wins}勝{sStat.losses}敗</span>
                        <span
                          class="win-rate-badge"
                          class:positive={sWinRate >= 50}
                          class:negative={sWinRate < 50}
                        >
                          {sWinRate.toFixed(1)}%
                        </span>
                      </span>
                    </li>
                  {/each}
                </ul>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    </div>
  {/if}
</div>

<style>
  .statistics-container {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    height: 100%;
    color: rgba(var(--theme-rgb-white), 0.9);
    overflow: auto;
    scrollbar-color: rgba(var(--theme-rgb-accent), 0.35) rgba(var(--theme-rgb-black), 0.2);
    scrollbar-width: thin;
  }

  .empty-state {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--text-secondary);
    width: 100%;
    box-sizing: border-box;
    padding: 3rem;
  }

  .empty-icon {
    font-size: 3rem;
    opacity: 0.5;
  }

  .empty-state p {
    margin: 0;
    font-size: 0.95rem;
    color: var(--text-secondary);
  }

  /* ---- サマリーカード ---- */
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    padding-top: 0.25rem;
  }

  .stat-card {
    position: relative;
    background: linear-gradient(
      145deg,
      rgba(var(--theme-rgb-accent), 0.06) 0%,
      rgba(var(--theme-rgb-surface-card), 0.85) 30%,
      rgba(var(--theme-rgb-surface-card-dark), 0.9) 100%
    );
    border: 1px solid rgba(var(--theme-rgb-white), 0.05);
    border-radius: calc(var(--glass-radius) - 6px);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    overflow: hidden;
    transition:
      transform 0.2s ease,
      border-color 0.2s ease,
      box-shadow 0.2s ease;
  }

  .stat-card:hover {
    border-color: rgba(var(--theme-rgb-accent), 0.2);
    box-shadow: 0 4px 16px rgba(var(--theme-rgb-black), 0.2);
    transform: translateY(-2px);
  }

  .stat-card.primary {
    background: linear-gradient(
      135deg,
      rgba(var(--theme-rgb-accent), 0.15) 0%,
      rgba(var(--theme-rgb-accent), 0.05) 100%
    );
    border-color: rgba(var(--theme-rgb-accent), 0.3);
  }

  .card-title {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 500;
    color: rgba(var(--theme-rgb-white), 0.7);
  }

  .card-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
    color: var(--accent-color);
    display: flex;
    align-items: baseline;
    gap: 0.2rem;
  }

  .card-value.positive {
    color: #4ade80;
  }
  .card-value.negative {
    color: #f87171;
  }

  .card-value.combo {
    font-size: 1.8rem;
    color: rgba(var(--theme-rgb-white), 0.9);
  }

  .card-value .unit {
    font-size: 1rem;
    font-weight: 500;
    color: rgba(var(--theme-rgb-white), 0.6);
  }

  .kill {
    color: #60a5fa;
  }
  .death {
    color: #f87171;
  }
  .separator {
    color: rgba(var(--theme-rgb-white), 0.3);
    margin: 0 0.2rem;
  }
  .special {
    color: #fcd34d;
  }

  .card-sub {
    font-size: 0.85rem;
    color: rgba(var(--theme-rgb-white), 0.6);
    margin-top: auto;
  }

  /* ---- ルール別カード ---- */
  .detail-card {
    position: relative;
    background: linear-gradient(
      145deg,
      rgba(var(--theme-rgb-accent), 0.06) 0%,
      rgba(var(--theme-rgb-surface-card), 0.85) 30%,
      rgba(var(--theme-rgb-surface-card-dark), 0.9) 100%
    );
    border: 1px solid rgba(var(--theme-rgb-white), 0.05);
    border-radius: calc(var(--glass-radius) - 6px);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-height: 0;
    overflow: hidden;
  }

  .detail-title {
    margin: 0;
    font-size: 1rem;
    color: rgba(var(--theme-rgb-white), 0.8);
    font-weight: 600;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(var(--theme-rgb-white), 0.1);
  }

  .scroll-list {
    overflow-y: auto;
    flex: 1;
    scrollbar-width: thin;
    scrollbar-color: rgba(var(--theme-rgb-accent), 0.3) rgba(var(--theme-rgb-black), 0.2);
  }

  /* ---- ルールリスト ---- */
  .rule-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .rule-row {
    border-radius: 6px;
    overflow: hidden;
  }

  .rule-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.6rem;
    background: rgba(var(--theme-rgb-white), 0.04);
    border: none;
    border-radius: 6px;
    color: inherit;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s ease;
    font-size: 0.9rem;
  }

  .rule-header:hover {
    background: rgba(var(--theme-rgb-accent), 0.1);
  }

  .chevron {
    font-size: 1.1rem;
    line-height: 1;
    color: rgba(var(--theme-rgb-white), 0.4);
    transition: transform 0.2s ease;
    display: inline-block;
    width: 1rem;
    text-align: center;
  }

  .chevron.open {
    transform: rotate(90deg);
    color: rgba(var(--theme-rgb-accent), 0.9);
  }

  .rule-name {
    flex: 1;
    color: rgba(var(--theme-rgb-white), 0.85);
    font-weight: 500;
  }

  .rule-meta,
  .stage-meta {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
  }

  .count {
    font-size: 0.85rem;
    color: rgba(var(--theme-rgb-white), 0.55);
  }

  .win-rate-badge {
    font-size: 0.85rem;
    font-weight: 600;
    min-width: 3.8rem;
    text-align: right;
  }

  .win-rate-badge.positive {
    color: #4ade80;
  }
  .win-rate-badge.negative {
    color: #f87171;
  }

  /* ---- ステージリスト ---- */
  .stage-list {
    list-style: none;
    padding: 0 0 0 1.5rem;
    margin: 0.2rem 0 0.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .stage-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.3rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
    background: rgba(var(--theme-rgb-white), 0.02);
  }

  .stage-name {
    color: rgba(var(--theme-rgb-white), 0.7);
  }
</style>
