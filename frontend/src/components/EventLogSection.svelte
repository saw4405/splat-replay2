<script>
  import { createEventDispatcher } from "svelte";
  import { formatTimestamp } from "../lib/format.js";

  export let events = [];

  const dispatch = createEventDispatcher();

  function refresh() {
    dispatch("refresh");
  }
</script>

<button class="refresh" on:click={refresh}>最新を取得</button>
<div class="event-list">
  {#if events.length === 0}
    <p>イベントはまだありません。</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>時刻</th>
          <th>種別</th>
          <th>詳細</th>
        </tr>
      </thead>
      <tbody>
        {#each [...events].reverse() as event, index (event.timestamp ?? index)}
          <tr>
            <td>{formatTimestamp(event.timestamp)}</td>
            <td>{event.type}</td>
            <td><pre>{JSON.stringify(event.payload, null, 2)}</pre></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>
