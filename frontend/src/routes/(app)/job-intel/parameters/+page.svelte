<script>
  // [IOD] iod_job_intel — Paramètres AppParameter
  import { enhance } from '$app/forms';
  import { invalidateAll } from '$app/navigation';
  import { toast } from 'svelte-sonner';
  import { tick } from 'svelte';
  import { Pencil, Check, X } from '@lucide/svelte';

  let { data, form } = $props();

  /** @type {string | null} */
  let editingKey = $state(null);
  let editingValue = $state('');
  let updateForm;
  let formKey = $state('');
  let formValue = $state('');

  function startEdit(param) {
    editingKey = param.key;
    editingValue = param.value;
  }

  function cancelEdit() {
    editingKey = null;
    editingValue = '';
  }

  async function saveEdit(param) {
    formKey = param.key;
    formValue = editingValue;
    await tick();
    updateForm.requestSubmit();
  }

  function updateEnhance() {
    return async ({ result }) => {
      if (result.type === 'success') {
        toast.success('Paramètre mis à jour');
        editingKey = null;
        await invalidateAll();
      } else {
        toast.error(result.data?.error || 'Erreur lors de la mise à jour');
      }
    };
  }

  $effect(() => {
    // Auto-dismiss si form success géré par enhance
    if (form?.success) editingKey = null;
  });
</script>

<svelte:head><title>Paramètres — Intelligence</title></svelte:head>

<!-- En-tête -->
<div class="border-b px-6 py-4">
  <h1 class="text-xl font-semibold">Paramètres</h1>
  <p class="text-muted-foreground mt-0.5 text-sm">Configuration du module Intelligence Emploi</p>
</div>

<!-- Liste des paramètres -->
<div class="flex-1 overflow-auto px-6 py-4">
  {#if data.parameters.length === 0}
    <p class="text-muted-foreground text-sm">Aucun paramètre trouvé.</p>
  {:else}
    <div class="divide-y rounded-lg border">
      {#each data.parameters as param}
        <div class="flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors">
          <div class="min-w-0 flex-1 pr-4">
            <p class="font-mono text-sm font-medium">{param.key}</p>
            {#if param.description}
              <p class="text-muted-foreground mt-0.5 text-xs">{param.description}</p>
            {/if}
          </div>
          <div class="flex items-center gap-2 shrink-0">
            {#if editingKey === param.key}
              <input
                type="text"
                bind:value={editingValue}
                onkeydown={(e) => {
                  if (e.key === 'Enter') saveEdit(param);
                  if (e.key === 'Escape') cancelEdit();
                }}
                class="border-input bg-background w-48 rounded border px-2 py-1 font-mono text-sm focus:outline-none focus:ring-1"
                autofocus
              />
              <button
                onclick={() => saveEdit(param)}
                class="text-green-600 hover:text-green-700 dark:text-green-400 p-1 rounded hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
                title="Enregistrer"
              ><Check class="size-4" strokeWidth={2} /></button>
              <button
                onclick={cancelEdit}
                class="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors"
                title="Annuler"
              ><X class="size-4" strokeWidth={2} /></button>
            {:else}
              <span class="font-mono text-sm text-muted-foreground">{param.value}</span>
              <button
                onclick={() => startEdit(param)}
                class="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
                title="Modifier"
              ><Pencil class="size-3.5" strokeWidth={1.75} /></button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Formulaire caché pour update -->
<form
  method="POST"
  action="?/update"
  bind:this={updateForm}
  use:enhance={updateEnhance}
  class="hidden"
>
  <input type="hidden" name="key" value={formKey} />
  <input type="hidden" name="value" value={formValue} />
</form>
