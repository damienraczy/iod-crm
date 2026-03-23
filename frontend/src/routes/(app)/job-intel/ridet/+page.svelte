<script>
  import { onDestroy } from 'svelte';
  import { goto, invalidateAll } from '$app/navigation';
  import { enhance, deserialize } from '$app/forms';
  import { toast } from 'svelte-sonner';
  import {
    Database, RefreshCw, CheckCircle2, AlertCircle,
    Clock, Info, CalendarDays, Search, X, Building2,
    MapPin, FileText, Save, Loader2, Users, Sparkles, Briefcase
  } from '@lucide/svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Progress } from '$lib/components/ui/progress/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';

  let { data } = $props();

  const isRunning = $derived(data.ridet.status === 'RUNNING');
  const isFailed  = $derived(data.ridet.status === 'FAILED');
  const isSuccess = $derived(data.ridet.status === 'SUCCESS');

  // Polling si import en cours
  let intervalId;
  $effect(() => {
    if (isRunning && !intervalId) {
      intervalId = setInterval(() => invalidateAll(), 3000);
    } else if (!isRunning && intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  });
  onDestroy(() => { if (intervalId) clearInterval(intervalId); });

  // ── Rafraîchissement RIDET ────────────────────────────────────────────────────
  let refreshLoading = $state(false);
  let refreshForm;
  function handleRefresh() {
    if (isRunning) return;
    refreshLoading = true;
    refreshForm.requestSubmit();
  }
  function handleRefreshEnhance() {
    return async ({ result }) => {
      refreshLoading = false;
      if (result.type === 'success') {
        toast.success('Mise à jour lancée en arrière-plan');
        await invalidateAll();
      } else {
        toast.error(result.data?.error || 'Erreur lors du lancement');
      }
    };
  }

  // ── Recherche ─────────────────────────────────────────────────────────────────
  let searchQuery = $state('');
  $effect(() => { searchQuery = data.q || ''; });
  let searchTimer;
  function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      if (searchQuery.trim().length >= 2) {
        params.set('q', searchQuery.trim());
      } else {
        params.delete('q');
      }
      goto(`?${params}`, { replaceState: true });
    }, 400);
  }

  // ── Panneau détail ────────────────────────────────────────────────────────────
  /** @type {any | null} */
  let selectedEntry = $state(null);
  let entryLoading = $state(false);
  let descriptionDraft = $state('');
  let descriptionDirty = $state(false);
  let savingDescription = $state(false);

  async function callAction(actionName, fields) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    const resp = await fetch(`?/${actionName}`, { method: 'POST', body: fd });
    const result = deserialize(await resp.text());
    if (result.type === 'failure' || result.type === 'error') {
      throw new Error(result.data?.error || `Erreur ${actionName}`);
    }
    return result.data;
  }

  async function openEntry(rid7) {
    if (selectedEntry?.rid7 === rid7) return;
    entryLoading = true;
    descriptionDirty = false;
    try {
      const res = await callAction('getEntry', { rid7 });
      selectedEntry = res.entry;
      descriptionDraft = res.entry.description || '';
    } catch (err) {
      toast.error(err.message || 'Erreur chargement établissement');
    } finally {
      entryLoading = false;
    }
  }

  function onDescriptionInput() {
    descriptionDirty = descriptionDraft !== (selectedEntry?.description ?? '');
  }

  let extracting = $state(false);
  async function extractRidet() {
    if (!selectedEntry || extracting) return;
    extracting = true;
    try {
      const res = await callAction('extractRidet', { rid7: selectedEntry.rid7 });
      selectedEntry = res.entry;
      descriptionDraft = res.entry.description || descriptionDraft;
      toast.success('Données RIDET extraites et consolidées');
    } catch (err) {
      toast.error(err.message || 'Erreur extraction RIDET');
    } finally {
      extracting = false;
    }
  }

  let consolidating = $state(false);
  async function consolidate() {
    if (!selectedEntry || consolidating) return;
    consolidating = true;
    try {
      const res = await callAction('consolidate', { rid7: selectedEntry.rid7 });
      selectedEntry = res.entry;
      descriptionDraft = res.entry.description || descriptionDraft;
      toast.success('Données Infogreffe consolidées');
    } catch (err) {
      toast.error(err.message || 'Erreur consolidation Infogreffe');
    } finally {
      consolidating = false;
    }
  }

  async function saveDescription() {
    if (!selectedEntry || savingDescription) return;
    savingDescription = true;
    try {
      const res = await callAction('saveDescription', {
        rid7: selectedEntry.rid7,
        description: descriptionDraft,
      });
      selectedEntry = res.entry;
      descriptionDirty = false;
      toast.success('Description enregistrée');
    } catch (err) {
      toast.error(err.message || 'Erreur enregistrement');
    } finally {
      savingDescription = false;
    }
  }

  function formatDate(isoString) {
    if (!isoString) return 'Jamais';
    return new Date(isoString).toLocaleString('fr-NC', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }
</script>

<svelte:head><title>Intelligence RIDET — IOD CRM</title></svelte:head>

<form method="POST" action="?/refresh" bind:this={refreshForm} use:enhance={handleRefreshEnhance} class="hidden"></form>

<div class="flex flex-col h-full bg-background">

  <!-- En-tête -->
  <div class="border-b px-6 py-4 flex items-center justify-between bg-white dark:bg-slate-950 shrink-0">
    <div>
      <h1 class="text-xl font-semibold flex items-center gap-2">
        <Database class="size-5 text-primary" />
        Référentiel RIDET
      </h1>
      <p class="text-muted-foreground mt-0.5 text-sm">Base des établissements actifs de Nouvelle-Calédonie</p>
    </div>
    <Button onclick={handleRefresh} disabled={isRunning || refreshLoading} class="gap-2">
      <RefreshCw class="size-4 {isRunning || refreshLoading ? 'animate-spin' : ''}" />
      Rafraîchir depuis data.gouv.nc
    </Button>
  </div>

  <div class="flex flex-1 overflow-hidden">

    <!-- Colonne gauche : statut + recherche + liste -->
    <div class="flex flex-col w-[420px] border-r overflow-hidden shrink-0">

      <!-- Statut import -->
      <div class="p-4 border-b space-y-3 shrink-0">
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-lg border px-3 py-2">
            <p class="text-[10px] font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-1">
              <Clock class="size-3" /> Dernière mise à jour
            </p>
            <p class="text-sm font-semibold mt-1">{formatDate(data.ridet.lastImport)}</p>
          </div>
          <div class="rounded-lg border px-3 py-2">
            <p class="text-[10px] font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-1">
              <Info class="size-3" /> État
            </p>
            <div class="mt-1">
              {#if isRunning}
                <Badge variant="outline" class="bg-blue-50 text-blue-700 border-blue-200 animate-pulse text-xs">En cours…</Badge>
              {:else if isSuccess}
                <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">
                  <CheckCircle2 class="size-3 mr-1" /> Opérationnel
                </Badge>
              {:else if isFailed}
                <Badge variant="outline" class="bg-red-50 text-red-700 border-red-200 text-xs">
                  <AlertCircle class="size-3 mr-1" /> Erreur
                </Badge>
              {:else}
                <Badge variant="outline" class="text-xs">En attente</Badge>
              {/if}
            </div>
          </div>
        </div>

        {#if isRunning}
          <div class="space-y-1">
            <div class="flex justify-between text-xs text-blue-600">
              <span>Import en cours…</span>
              <span class="font-mono">{data.ridet.progress}%</span>
            </div>
            <Progress value={data.ridet.progress} class="h-2 bg-blue-100" />
          </div>
        {/if}

        {#if isFailed && data.ridet.lastError}
          <p class="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1.5 font-mono">
            {data.ridet.lastError}
          </p>
        {/if}
      </div>

      <!-- Recherche -->
      <div class="p-3 border-b shrink-0">
        <div class="relative">
          <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Rechercher un établissement…"
            bind:value={searchQuery}
            oninput={onSearchInput}
            class="w-full pl-8 pr-8 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1"
          />
          {#if searchQuery}
            <button
              onclick={() => { searchQuery = ''; goto('?', { replaceState: true }); }}
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X class="size-3.5" />
            </button>
          {/if}
        </div>
      </div>

      <!-- Liste des résultats -->
      <div class="flex-1 overflow-y-auto">
        {#if data.entries.length === 0}
          <div class="p-6 text-center text-sm text-muted-foreground">
            {#if searchQuery.trim().length >= 2}
              Aucun résultat pour « {searchQuery} »
            {:else}
              Tapez au moins 2 caractères pour rechercher
            {/if}
          </div>
        {:else}
          <div class="divide-y">
            {#each data.entries as entry}
              <button
                onclick={() => openEntry(entry.rid7)}
                class="w-full text-left px-4 py-3 hover:bg-muted/50 transition-colors {selectedEntry?.rid7 === entry.rid7 ? 'bg-primary/5 border-l-2 border-primary' : ''}"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="text-sm font-medium truncate">{entry.denomination || entry.enseigne || entry.rid7}</p>
                    {#if entry.enseigne && entry.enseigne !== entry.denomination}
                      <p class="text-xs text-muted-foreground truncate">{entry.enseigne}</p>
                    {/if}
                    <div class="flex items-center gap-2 mt-0.5">
                      <span class="text-[10px] font-mono text-muted-foreground">{entry.rid7}</span>
                      {#if entry.commune}
                        <span class="text-[10px] text-muted-foreground flex items-center gap-0.5">
                          <MapPin class="size-2.5" />{entry.commune}
                        </span>
                      {/if}
                    </div>
                  </div>
                  {#if entry.description}
                    <FileText class="size-3.5 text-primary shrink-0 mt-0.5" title="Description renseignée" />
                  {/if}
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Panneau détail -->
    <div class="flex-1 overflow-y-auto">
      {#if entryLoading}
        <div class="flex items-center justify-center h-full text-muted-foreground gap-2">
          <Loader2 class="size-5 animate-spin" />
          Chargement…
        </div>
      {:else if selectedEntry}
        <div class="p-6 space-y-6 max-w-2xl">

          <!-- Identité -->
          <div>
            <h2 class="text-xl font-semibold">{selectedEntry.denomination || selectedEntry.enseigne}</h2>
            {#if selectedEntry.enseigne && selectedEntry.enseigne !== selectedEntry.denomination}
              <p class="text-muted-foreground text-sm mt-0.5">{selectedEntry.enseigne}</p>
            {/if}
            <div class="flex items-center gap-3 mt-2 flex-wrap">
              <span class="font-mono text-xs bg-muted px-2 py-0.5 rounded">{selectedEntry.rid7}</span>
              {#if selectedEntry.forme_juridique}
                <span class="text-xs text-muted-foreground">{selectedEntry.forme_juridique}</span>
              {/if}
              {#if selectedEntry.commune}
                <span class="text-xs text-muted-foreground flex items-center gap-1">
                  <MapPin class="size-3" />{selectedEntry.commune}{selectedEntry.province ? ` · ${selectedEntry.province}` : ''}
                </span>
              {/if}
            </div>
          </div>

          <!-- Navigation rapide -->
          <div class="flex gap-2 flex-wrap">
            <a
              href="/job-intel/offers?rid7={selectedEntry.rid7}"
              class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
            >
              <Briefcase class="size-3.5" />
              Voir les offres
            </a>
            {#if selectedEntry.denomination || selectedEntry.enseigne}
              <a
                href="/job-intel/offers?q={encodeURIComponent(selectedEntry.denomination || selectedEntry.enseigne)}"
                class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
              >
                <Search class="size-3.5" />
                Rechercher dans les offres
              </a>
            {/if}
          </div>

          <!-- Actions de consolidation -->
          <div class="flex gap-2 flex-wrap">
            <button
              onclick={extractRidet}
              disabled={extracting}
              class="inline-flex items-center gap-1.5 rounded-md border border-green-300 bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 disabled:opacity-50 transition-colors dark:border-green-800 dark:bg-green-900/20 dark:text-green-400"
            >
              {#if extracting}
                <Loader2 class="size-3.5 animate-spin" />
                Extraction en cours…
              {:else}
                <Sparkles class="size-3.5" />
                Consolider RIDET (PDF)
              {/if}
            </button>
            <button
              onclick={consolidate}
              disabled={consolidating}
              class="inline-flex items-center gap-1.5 rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-400"
            >
              {#if consolidating}
                <Loader2 class="size-3.5 animate-spin" />
                Interrogation…
              {:else}
                <RefreshCw class="size-3.5" />
                Interroger Infogreffe
              {/if}
            </button>
          </div>

          <!-- Données Infogreffe -->
          <div class="rounded-lg border border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-900/10 p-4 space-y-2">
            <div class="flex items-center justify-between">
              <p class="text-[10px] font-bold uppercase tracking-widest text-blue-700 dark:text-blue-400">Données consolidées — Infogreffe.nc</p>
            </div>
            {#if selectedEntry.adresse}
              <p class="text-sm"><span class="text-xs text-muted-foreground">Adresse :</span> {selectedEntry.adresse}</p>
            {/if}
            {#if selectedEntry.code_naf}
              <p class="text-sm"><span class="text-xs text-muted-foreground">Activité (NAF) :</span> {selectedEntry.code_naf} — {selectedEntry.activite_principale}</p>
            {/if}
            {#if !selectedEntry.adresse && !selectedEntry.code_naf && !selectedEntry.activite_principale}
              <p class="text-xs text-blue-500/70 italic">Aucune donnée consolidée — cliquez sur "Interroger Infogreffe"</p>
            {/if}
          </div>

          <!-- Dirigeants -->
          {#if selectedEntry.dirigeants?.length > 0}
            <div>
              <p class="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <Users class="size-3.5" /> Dirigeants & Représentants
              </p>
              <div class="space-y-1">
                {#each selectedEntry.dirigeants as dir}
                  <p class="text-sm">{dir}</p>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Description éditoriale -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label for="ridet-description" class="text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                <FileText class="size-3.5" /> Contexte éditorial
              </label>
              <span class="text-[10px] text-muted-foreground italic">
                Non écrasé lors des mises à jour du référentiel
              </span>
            </div>
            <textarea
              id="ridet-description"
              bind:value={descriptionDraft}
              oninput={onDescriptionInput}
              rows="6"
              placeholder="Contexte sur l'entreprise, notes commerciales, particularités…"
              class="w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 resize-y"
            ></textarea>
            {#if descriptionDirty}
              <div class="flex items-center gap-2">
                <button
                  onclick={saveDescription}
                  disabled={savingDescription}
                  class="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {#if savingDescription}
                    <Loader2 class="size-3.5 animate-spin" />
                  {:else}
                    <Save class="size-3.5" />
                  {/if}
                  Enregistrer
                </button>
                <button
                  onclick={() => { descriptionDraft = selectedEntry.description || ''; descriptionDirty = false; }}
                  class="text-sm text-muted-foreground hover:text-foreground"
                >Annuler</button>
              </div>
            {/if}
            {#if selectedEntry.updated_at}
              <p class="text-[10px] text-muted-foreground">
                Dernière modification : {formatDate(selectedEntry.updated_at)}
              </p>
            {/if}
          </div>

        </div>
      {:else}
        <div class="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
          <Building2 class="size-10 opacity-20" />
          <p class="text-sm">Sélectionnez un établissement pour voir ses détails</p>
        </div>
      {/if}
    </div>

  </div>
</div>
