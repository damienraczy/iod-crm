<script>
  import { onMount, onDestroy } from 'svelte';
  import { invalidateAll } from '$app/navigation';
  import { enhance } from '$app/forms';
  import { toast } from 'svelte-sonner';
  import { 
    Database, 
    RefreshCw, 
    CheckCircle2, 
    AlertCircle, 
    Clock, 
    Info,
    CalendarDays
  } from '@lucide/svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import { Progress } from '$lib/components/ui/progress/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';

  let { data, form } = $props();
  let loading = $state(false);
  let intervalId;
  let refreshForm;

  const isRunning = $derived(data.ridet.status === 'RUNNING');
  const isFailed = $derived(data.ridet.status === 'FAILED');
  const isSuccess = $derived(data.ridet.status === 'SUCCESS');

  function handleRefresh() {
    if (isRunning) return;
    loading = true;
    refreshForm.requestSubmit();
  }

  function handleEnhance() {
    return async ({ result }) => {
      loading = false;
      if (result.type === 'success') {
        toast.success("Mise à jour lancée en arrière-plan");
        await invalidateAll();
      } else if (result.type === 'failure' || result.data?.error) {
        toast.error(result.data?.error || "Erreur lors du lancement");
      }
    };
  }

  // Polling si en cours
  $effect(() => {
    if (isRunning && !intervalId) {
      intervalId = setInterval(() => {
        invalidateAll();
      }, 3000);
    } else if (!isRunning && intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  });

  onMount(() => {
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  });

  function formatDate(isoString) {
    if (!isoString) return 'Jamais';
    try {
      return new Date(isoString).toLocaleString('fr-NC', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return 'Inconnue';
    }
  }
</script>

<svelte:head><title>Intelligence RIDET — IOD CRM</title></svelte:head>

<div class="flex flex-col h-full bg-background">
  <!-- Formulaire caché (Server-side) -->
  <form method="POST" action="?/refresh" bind:this={refreshForm} use:enhance={handleEnhance} class="hidden"></form>

  <!-- En-tête -->
  <div class="border-b px-6 py-4 flex items-center justify-between bg-white dark:bg-slate-950">
    <div>
      <h1 class="text-xl font-semibold flex items-center gap-2">
        <Database class="size-5 text-primary" />
        Référentiel RIDET
      </h1>
      <p class="text-muted-foreground mt-0.5 text-sm">Gestion de la base de données des entreprises de Nouvelle-Calédonie</p>
    </div>
    
    <Button 
      onclick={handleRefresh} 
      disabled={isRunning || loading}
      class="gap-2"
    >
      <RefreshCw class="size-4 {isRunning || loading ? 'animate-spin' : ''}" />
      Rafraîchir depuis data.gouv.nc
    </Button>
  </div>

  <div class="flex-1 overflow-auto p-6 space-y-6">
    
    <!-- Statut Actuel -->
    <div class="grid gap-6 md:grid-cols-3">
      <Card.Root>
        <Card.Header class="pb-2">
          <Card.Title class="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Clock class="size-4" />
            Dernière mise à jour
          </Card.Title>
        </Card.Header>
        <Card.Content>
          <div class="text-2xl font-bold">{formatDate(data.ridet.lastImport)}</div>
          <p class="text-xs text-muted-foreground mt-1">Source : data.gouv.nc (CSV complet)</p>
        </Card.Content>
      </Card.Root>

      <Card.Root>
        <Card.Header class="pb-2">
          <Card.Title class="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Info class="size-4" />
            État du service
          </Card.Title>
        </Card.Header>
        <Card.Content>
          <div class="flex items-center gap-2">
            {#if isRunning}
              <Badge variant="outline" class="bg-blue-50 text-blue-700 border-blue-200 animate-pulse">
                Import en cours...
              </Badge>
            {:else if isSuccess}
              <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200">
                <CheckCircle2 class="size-3 mr-1" /> Opérationnel
              </Badge>
            {:else if isFailed}
              <Badge variant="outline" class="bg-red-50 text-red-700 border-red-200">
                <AlertCircle class="size-3 mr-1" /> Erreur
              </Badge>
            {:else}
              <Badge variant="outline">En attente</Badge>
            {/if}
          </div>
          <p class="text-xs text-muted-foreground mt-2">
            {isRunning ? 'Le téléchargement peut prendre plusieurs minutes.' : 'Prêt pour une nouvelle synchronisation.'}
          </p>
        </Card.Content>
      </Card.Root>

      <Card.Root>
        <Card.Header class="pb-2">
          <Card.Title class="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <CalendarDays class="size-4" />
            Prochaine synchro
          </Card.Title>
        </Card.Header>
        <Card.Content>
          <div class="text-2xl font-bold">Manuelle</div>
          <p class="text-xs text-muted-foreground mt-1">Gérée par l'administrateur</p>
        </Card.Content>
      </Card.Root>
    </div>

    <!-- Section Progression (si en cours) -->
    {#if isRunning}
      <Card.Root class="border-blue-200 bg-blue-50/30">
        <Card.Header>
          <Card.Title class="text-lg flex items-center justify-between">
            <span class="flex items-center gap-2">
              <RefreshCw class="size-5 text-blue-600 animate-spin" />
              Mise à jour du référentiel en cours
            </span>
            <span class="text-blue-600 font-mono">{data.ridet.progress}%</span>
          </Card.Title>
          <Card.Description>
            Ne fermez pas cette page pour suivre la progression en temps réel.
          </Card.Description>
        </Card.Header>
        <Card.Content>
          <Progress value={data.ridet.progress} class="h-3 bg-blue-100" />
          <p class="text-sm text-blue-600 mt-4 flex items-center gap-2 italic">
            <Info class="size-4" />
            Environ 160 000 établissements sont en cours de traitement...
          </p>
        </Card.Content>
      </Card.Root>
    {/if}

    <!-- Message d'erreur -->
    {#if isFailed && data.ridet.lastError}
      <div class="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 flex items-start gap-3">
        <AlertCircle class="size-5 mt-0.5" />
        <div>
          <p class="font-semibold">L'importation a échoué</p>
          <p class="text-sm font-mono mt-1 opacity-80">{data.ridet.lastError}</p>
          <Button variant="outline" size="sm" class="mt-3 border-red-300 text-red-800 hover:bg-red-100" onclick={handleRefresh}>
            Réessayer maintenant
          </Button>
        </div>
      </div>
    {/if}

    <!-- Guide d'utilisation -->
    <Card.Root>
      <Card.Header>
        <Card.Title>Informations sur le référentiel</Card.Title>
      </Card.Header>
      <Card.Content class="prose dark:prose-invert max-w-none text-sm text-muted-foreground">
        <p>
          Le référentiel RIDET (Répertoire des Entreprises et des Établissements) est indispensable au bon fonctionnement du module d'intelligence. Il permet :
        </p>
        <ul class="list-disc pl-5 space-y-2 mt-2">
          <li><strong>L'identification automatique</strong> des entreprises lors du scraping d'offres d'emploi.</li>
          <li><strong>Le croisement de données</strong> avec les comptes CRM existants.</li>
          <li><strong>L'analyse contextuelle</strong> par l'IA (secteur d'activité, localisation, forme juridique).</li>
        </ul>
        <div class="mt-4 p-3 bg-muted/50 rounded-md border border-dashed text-xs italic">
          <strong>Note technique :</strong> Les données sont récupérées via l'export JSON officiel de data.gouv.nc. Le processus remplace ou met à jour les entrées existantes sans vider la base (upsert) pour préserver les liens avec vos comptes.
        </div>
      </Card.Content>
    </Card.Root>

  </div>
</div>

<style>
  :global(.dark) Card.Root {
    background-color: rgb(15 23 42 / 0.5);
  }
</style>
