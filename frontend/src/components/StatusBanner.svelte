<script>
  export let statusMessage = "";
  export let errorMessage = "";
</script>

{#if statusMessage}
  <div class="notice success">{statusMessage}</div>
{/if}
{#if errorMessage}
  <div class="notice error">{errorMessage}</div>
{/if}
