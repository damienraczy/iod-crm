<script>
  import { X, Building, CheckCircle2 } from '@lucide/svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';

  /**
   * @typedef {Object} Props
   * @property {Array} results - Liste des candidats RIDET
   * @property {string} query - Le nom de l'entreprise recherché
   * @property {Function} onSelect - Callback lors de la sélection (rid7)
   * @property {Function} onClose - Callback de fermeture
   */
  
  /** @type {Props} */
  let { results = [], query = '', onSelect, onClose } = $props();

  function select(rid7) {
    onSelect(rid7);
    onClose();
  }
</script>

<div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
  <div class="bg-background border rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[85vh]">
    
    <!-- Header -->
    <div class="px-6 py-4 border-b flex items-center justify-between">
      <div>
        <h3 class="text-lg font-semibold italic">Sélectionner l'établissement</h3>
        <p class="text-muted-foreground text-sm">Candidats trouvés pour : <span class="font-bold text-foreground">"{query}"</span></p>
      </div>
      <Button variant="ghost" size="sm" onclick={onClose}>
        <X class="size-4" />
      </Button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-4 space-y-2">
      {#each results as entry}
        <button
          class="w-full text-left p-4 rounded-lg border hover:bg-muted/50 transition-all group flex items-start gap-4"
          ondblclick={() => select(entry.rid7)}
          onclick={() => {/* Click simple pourrait aussi sélectionner si on veut */}}
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between mb-1">
              <span class="font-bold text-sm text-primary uppercase">
                {entry.denomination || entry.enseigne}
              </span>
              <div class="flex items-center gap-2">
                <span class="font-mono text-[11px] bg-muted px-2 py-0.5 rounded border border-dashed">
                  {entry.rid7}
                </span>
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded {entry.score >= 80 ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}">
                  {entry.score}%
                </span>
              </div>
            </div>
            
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
              <div class="flex items-center gap-1.5">
                <Building class="size-3" />
                <span>{entry.commune}</span>
              </div>
              {#if entry.sigle}
                <div class="flex items-center gap-1.5 italic">
                  <span>({entry.sigle})</span>
                </div>
              {/if}
              <div class="flex items-center gap-1.5">
                <span>·</span>
                <span>{entry.forme_juridique}</span>
              </div>
            </div>
          </div>
          
          <Button 
            variant="outline" 
            size="sm" 
            class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity gap-1"
            onclick={() => select(entry.rid7)}
          >
            Choisir <CheckCircle2 class="size-3" />
          </Button>
        </button>
      {/each}
    </div>

    <!-- Footer -->
    <div class="px-6 py-4 border-t bg-muted/20 text-[11px] text-muted-foreground flex items-center justify-between">
      <span>Double-cliquez sur une ligne pour valider rapidement.</span>
      <span>{results.length} résultats trouvés.</span>
    </div>
  </div>
</div>
