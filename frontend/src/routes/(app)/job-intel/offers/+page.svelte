<script>
  // [IOD] iod_job_intel — Offres d'emploi
  import { page } from '$app/stores';
  import { goto, invalidateAll } from '$app/navigation';
  import { tick } from 'svelte';
  import RidetFuzzyDialog from '$lib/components/job-intel/RidetFuzzyDialog.svelte';
  import { enhance, deserialize } from '$app/forms';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
  import {
    RefreshCw, ExternalLink, ChevronLeft, ChevronRight,
    Search, X, Brain, Save, Loader2, Zap,
    MessageSquare, Mail, Stethoscope, Sparkles, Building2,
    Users, Building
  } from '@lucide/svelte';

  /** @type {{ data: import('./$types').PageData, form: import('./$types').ActionData }} */
  let { data, form } = $props();

  // ── Filtres ──────────────────────────────────────────────────────────────────
  let searchInput = $state(data.filters.q);
  let sourceFilter = $state(data.filters.source);
  let statusFilter = $state(data.filters.status);

  const SOURCES = [
    { value: '', label: 'Toutes les sources' },
    { value: 'GOUV_NC', label: 'Emploi Gouv NC' },
    { value: 'PSUD', label: 'Province Sud' },
    { value: 'JOB_NC', label: 'Job.nc' },
    { value: 'LEMPLOI_NC', label: "L'Emploi.nc" }
  ];

  const STATUSES = [
    { value: '', label: 'Tous les statuts' },
    { value: 'NEW', label: 'Nouvelle' },
    { value: 'PUBLIEE', label: 'Publiée' },
    { value: 'ARCHIVEE', label: 'Archivée' }
  ];

  const CONTRACT_TYPES = ['CDI', 'CDD', 'Intérim', 'Stage', 'Alternance', 'Freelance', 'Autre'];

  const STATUS_COLORS = {
    NEW:      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    PUBLIEE:  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    ARCHIVEE: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  };

  const SOURCE_COLORS = {
    GOUV_NC:    'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    PSUD:       'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    JOB_NC:     'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
    LEMPLOI_NC: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400'
  };

  const EVAL_LABELS = {
    eval_n4: 'N4', eval_n5: 'N5', eval_n6: 'N6', eval_n7: 'N7', eval_n8: 'N8'
  };
  const EVAL_COLORS = {
    eval_n4: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    eval_n5: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
    eval_n6: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
    eval_n7: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
    eval_n8: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  };

  const AI_ACTIONS = [
    { key: 'skill-analysis',    label: 'Compétences critiques', icon: Brain,         type: 'skill_analysis' },
    { key: 'ice-breaker',       label: 'Ice breaker',           icon: Sparkles,      type: 'ice_breaker' },
    { key: 'diagnostic',        label: 'Diagnostic offre',      icon: Stethoscope,   type: 'offer_diagnostic' },
    { key: 'questions-offre',   label: 'Questions brûlantes',   icon: MessageSquare, type: 'questions_offre' },
    { key: 'email-job',         label: 'Email prospection',     icon: Mail,          type: 'email_job' },
  ];

  const COMPANY_AI_ACTIONS = [
    { key: 'questions-company', label: 'Questions entreprise', icon: MessageSquare, type: 'questions_company' },
    { key: 'email-general',     label: 'Email général',        icon: Mail,          type: 'email_general' },
  ];

  async function applyFilters() {
    const url = new URL($page.url);
    url.searchParams.set('page', '1');
    if (searchInput) url.searchParams.set('q', searchInput); else url.searchParams.delete('q');
    if (sourceFilter) url.searchParams.set('source', sourceFilter); else url.searchParams.delete('source');
    if (statusFilter) url.searchParams.set('status', statusFilter); else url.searchParams.delete('status');
    await goto(url.toString(), { replaceState: true, noScroll: true, invalidateAll: true });
  }

  async function clearFilters() {
    searchInput = ''; sourceFilter = ''; statusFilter = '';
    await goto('/job-intel/offers', { replaceState: true, noScroll: true, invalidateAll: true });
  }

  const activeFiltersCount = $derived(
    [data.filters.q, data.filters.source, data.filters.status].filter(Boolean).length
  );

  // ── Pagination ────────────────────────────────────────────────────────────────
  async function changePage(newPage) {
    const url = new URL($page.url);
    url.searchParams.set('page', newPage.toString());
    await goto(url.toString(), { replaceState: true, noScroll: true, invalidateAll: true });
  }

  // ── Drawer ────────────────────────────────────────────────────────────────────
  let drawerOpen = $state(false);
  let drawerTab = $state('detail'); // 'detail' | 'edit' | 'ia'
  /** @type {any} */
  let selectedOffer = $state(null);
  let offerAnalyses = $state([]);
  let loadingAnalyses = $state(false);

  // Entreprise / RIDET
  /** @type {any | null} */
  let ridetDetail = $state(null);
  let isConsolidating = $state(false);

  // Edition
  let editData = $state({});
  let isSavingOffer = $state(false);

  // CRM Account link (lecture seule au chargement)
  /** @type {{ id: string, name: string, rid7: string } | null} */
  let crmAccount = $state(null);

  // Action commerciale orchestrée
  let actionLoading = $state(false);
  /**
   * @type {{
   *   eval_category: { code: string, label: string },
   *   account: { id: string, name: string, rid7: string, created: boolean },
   *   contacts: Array<{ id: string, name: string, title: string }>,
   *   product: { id: string, name: string, price: string, currency: string } | null
   * } | null}
   */
  let actionResult = $state(null);

  // Formulaire opportunité
  let showProspectForm = $state(false);
  let prospectName = $state('');
  let prospectEmailDraft = $state('');
  let prospectCreating = $state(false);

  // IA
  /** @type {string | null} */
  let runningAction = $state(null);
  let iaOutput = $state('');
  let iaOutputType = $state('');
  /** @type {Set<number>} analyses dépliées (par id) */
  let expandedAnalyses = $state(new Set());

  // ── Utilitaire : appel d'une server action depuis le client ──────────────────
  /**
   * Appelle une server action SvelteKit (?/actionName) via fetch.
   * Les server actions utilisent le cookie JWT → pas de problème d'auth client-side.
   * @param {string} actionName
   * @param {Record<string, string>} fields
   * @returns {Promise<any>} data retournée par l'action
   */
  async function callAction(actionName, fields) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    const resp = await fetch(`?/${actionName}`, { method: 'POST', body: fd });
    const result = deserialize(await resp.text());
    if (result.type === 'failure' || result.type === 'error') {
      throw new Error(result.data?.error || result.error?.message || `Erreur action ${actionName}`);
    }
    return result.data;
  }

  function openOffer(offer) {
    // 1. Ouverture immédiate du tiroir
    selectedOffer = offer;
    drawerOpen = true;
    drawerTab = 'detail';
    
    // Reset des états
    iaOutput = '';
    iaOutputType = '';
    crmAccount = null;
    actionResult = null;
    actionLoading = false;
    showProspectForm = false;
    ridetDetail = null;
    prospectName = `${offer.title} - ${offer.company_name}`;
    prospectEmailDraft = '';
    
    editData = {
      title: offer.title,
      location: offer.location || '',
      contract_type: offer.contract_type || '',
      experience_req: '',
      education_req: '',
      nb_postes: 1,
      score: offer.score || 0,
      status: offer.status,
      description: '',
    };

    // 2. Lancement asynchrone en arrière-plan
    loadAllOfferData(offer);
  }

  async function loadAllOfferData(offer) {
    try {
      // Détails
      const detailData = await callAction('getOffer', { id: String(offer.id) });
      selectedOffer = detailData.offer;
      editData = {
        ...editData,
        experience_req: detailData.offer.experience_req || '',
        education_req: detailData.offer.education_req || '',
        nb_postes: detailData.offer.nb_postes || 1,
        description: detailData.offer.description || '',
      };

      // Analyses
      await loadAnalyses(offer.id);

      // CRM — vérifier si un compte existe déjà
      if (offer.rid7) {
        try {
          const res = await callAction('crmAccount', { rid7: offer.rid7 });
          crmAccount = res.found ? res.account : null;
        } catch { crmAccount = null; }

        // Données consolidées locales (dirigeants, etc.)
        try {
          const rData = await callAction('getRidet', { rid7: offer.rid7 });
          ridetDetail = rData.result;
        } catch {
          ridetDetail = null;
        }
      }
    } catch (err) {
      console.error('Erreur chargement données offer:', err);
    }
  }

  async function fetchFullDetail() {
    if (!selectedOffer) return;
    try {
      const data = await callAction('getOffer', { id: String(selectedOffer.id) });
      selectedOffer = data.offer;
      editData = {
        title: data.offer.title,
        location: data.offer.location || '',
        contract_type: data.offer.contract_type || '',
        experience_req: data.offer.experience_req || '',
        education_req: data.offer.education_req || '',
        nb_postes: data.offer.nb_postes || 1,
        score: data.offer.score || 0,
        status: data.offer.status,
        description: data.offer.description || '',
      };
      toast.success('Détails chargés');
    } catch (err) {
      toast.error('Erreur lors du chargement des détails');
    }
  }

  async function startAction() {
    if (!selectedOffer || actionLoading) return;
    actionLoading = true;
    try {
      const res = await callAction('startAction', { offerId: String(selectedOffer.id) });
      actionResult = res.result;
      crmAccount = res.result.account;
      const nb = res.result.contacts.length;
      toast.success(
        `${res.result.eval_category.label} · compte ${res.result.account.created ? 'créé' : 'existant'}` +
        (nb ? ` · ${nb} contact${nb > 1 ? 's' : ''}` : '')
      );
    } catch (err) {
      toast.error(err.message || 'Erreur action commerciale');
    } finally {
      actionLoading = false;
    }
  }

  async function loadAnalyses(offerId) {
    loadingAnalyses = true;
    offerAnalyses = [];
    try {
      const data = await callAction('getAnalyses', { id: String(offerId) });
      offerAnalyses = data.analyses || [];
    } catch {
      offerAnalyses = [];
    } finally {
      loadingAnalyses = false;
    }
  }

  function closeDrawer() {
    drawerOpen = false;
    selectedOffer = null;
    offerAnalyses = [];
    iaOutput = '';
    expandedAnalyses = new Set();
  }

  function toggleAnalysis(id) {
    const next = new Set(expandedAnalyses);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedAnalyses = next;
  }

  async function deleteAnalysis(id) {
    try {
      await callAction('deleteAnalysis', { id: String(id) });
      offerAnalyses = offerAnalyses.filter(a => a.id !== id);
      const next = new Set(expandedAnalyses);
      next.delete(id);
      expandedAnalyses = next;
      toast.success('Analyse supprimée');
    } catch (err) {
      toast.error(err.message || 'Erreur suppression');
    }
  }

  // ── Démarche commerciale ──────────────────────────────────────────────────────
  function openProspectForm() {
    const cat = actionResult?.eval_category?.label || '';
    prospectName = cat
      ? `Évaluation ${cat} — ${selectedOffer?.company_name || ''}`
      : `Prospection — ${selectedOffer?.title || ''}`;
    const lastEmail = offerAnalyses.find(a => a.analysis_type === 'email_job');
    prospectEmailDraft = lastEmail?.result_text || '';
    showProspectForm = true;
  }

  async function createProspect() {
    const account = actionResult?.account ?? crmAccount;
    if (!account || !prospectName.trim() || prospectCreating) return;
    prospectCreating = true;
    try {
      const product = actionResult?.product;
      await callAction('createOpportunity', {
        name: prospectName.trim(),
        accountId: account.id,
        description: prospectEmailDraft,
        leadSource: selectedOffer?.source || 'OTHER',
        ...(product ? {
          productId: product.id,
          productName: product.name,
          unitPrice: product.price,
        } : {}),
      });
      toast.success('Opportunité créée');
      showProspectForm = false;
      await goto(`/accounts/${account.id}`);
    } catch (err) {
      toast.error(err.message || 'Erreur création opportunité');
    } finally {
      prospectCreating = false;
    }
  }

  // ── Compte CRM ────────────────────────────────────────────────────────────────
  async function linkCRMAccount() {
    if (!selectedOffer?.rid7 || crmAccountLoading) return;
    crmAccountLoading = true;
    try {
      const res = await callAction('crmAccount', { rid7: selectedOffer.rid7, create: 'true' });
      crmAccount = res.account;
      crmContacts = res.contacts ?? [];
      const contactsMsg = crmContacts.length ? ` — ${crmContacts.length} contact(s) importé(s)` : '';
      toast.success((res.created ? 'Compte CRM créé' : 'Compte CRM existant retrouvé') + contactsMsg);
    } catch (err) {
      toast.error(err.message || 'Erreur création compte CRM');
    } finally {
      crmAccountLoading = false;
    }
  }

  // ── Sauvegarde offre ──────────────────────────────────────────────────────────
  async function saveOffer() {
    if (!selectedOffer || isSavingOffer) return;
    isSavingOffer = true;
    try {
      const data = await callAction('patchOffer', {
        id: String(selectedOffer.id),
        data: JSON.stringify(editData)
      });
      selectedOffer = { ...selectedOffer, ...data.offer };
      toast.success('Offre mise à jour');
      drawerTab = 'detail';
      await invalidateAll();
    } catch (err) {
      toast.error(err.message || 'Erreur lors de la sauvegarde');
    } finally {
      isSavingOffer = false;
    }
  }

  // ── Actions IA ────────────────────────────────────────────────────────────────
  async function runAI(actionKey, isCompany = false) {
    if (!selectedOffer || runningAction) return;
    runningAction = actionKey;
    iaOutput = '';
    iaOutputType = actionKey;

    try {
      let body = {};
      if (isCompany && actionKey === 'questions-company') {
        body = { offer_title: selectedOffer.title, description: selectedOffer.description || '' };
      }

      const data = await callAction('runAI', {
        offerId:   String(selectedOffer.id),
        actionKey,
        isCompany: String(isCompany),
        rid7:      selectedOffer.rid7 || '',
        body:      JSON.stringify(body)
      });

      const analysis = data.analysis;
      iaOutput = analysis.result_text || JSON.stringify(analysis.result_json, null, 2) || '';
      offerAnalyses = [analysis, ...offerAnalyses];
      // Pré-ouvrir l'analyse dans l'onglet Détail
      expandedAnalyses = new Set([analysis.id, ...expandedAnalyses]);
      toast.success('Analyse générée');
    } catch (err) {
      toast.error(err.message || 'Erreur IA');
      iaOutput = '';
    } finally {
      runningAction = null;
    }
  }

  // ── Sync ──────────────────────────────────────────────────────────────────────
  let syncForm;
  let syncSources = $state('');
  let isSyncing = $state(false);

  function syncEnhance() {
    isSyncing = true;
    return async ({ result }) => {
      isSyncing = false;
      if (result.type === 'success') {
        toast.success('Synchronisation déclenchée');
        await invalidateAll();
      } else {
        toast.error(result.data?.error || 'Erreur de synchronisation');
      }
    };
  }

  async function triggerSync(sources) {
    syncSources = sources ? JSON.stringify(sources) : '';
    await tick();
    syncForm.requestSubmit();
  }

  // ── Utilitaires ───────────────────────────────────────────────────────────────
  function scoreColor(score) {
    if (score >= 70) return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
    if (score >= 40) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400';
    return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400';
  }

  function formatDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }

  function analysisTypeLabel(type) {
    return AI_ACTIONS.find(a => a.type === type)?.label
      || COMPANY_AI_ACTIONS.find(a => a.type === type)?.label
      || type;
  }

  // ── RID7 (Assignation) ───────────────────────────────────────────────────────
  let ridetSearchQuery = $state('');
  let ridetSearchResults = $state([]);
  let isSearchingRidet = $state(false);
  let searchTimer;

  async function searchRidet() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      if (!ridetSearchQuery || ridetSearchQuery.length < 2) {
        ridetSearchResults = [];
        return;
      }
      isSearchingRidet = true;
      try {
        const data = await callAction('matchRidet', { q: ridetSearchQuery });
        ridetSearchResults = data.result?.results || [];
      } catch (err) {
        console.error('Recherche RIDET error:', err);
        toast.error('Erreur recherche RIDET');
      } finally {
        isSearchingRidet = false;
      }
    }, 400);
  }

  async function updateOfferRID7(newRid7) {
    if (!selectedOffer) return;
    try {
      await callAction('patchOffer', {
        id: String(selectedOffer.id),
        data: JSON.stringify({ rid7: newRid7 })
      });
      toast.success(newRid7 ? 'RID7 assigné' : 'RID7 effacé');
      selectedOffer.rid7 = newRid7;
      ridetSearchResults = [];
      ridetSearchQuery = '';
      await invalidateAll();
    } catch (err) {
      toast.error(err.message || 'Erreur lors de la mise à jour');
    }
  }

  async function consolidateRidet() {
    if (!selectedOffer || !selectedOffer.rid7) return;
    isConsolidating = true;
    try {
      const data = await callAction('consolidateRidet', { rid7: selectedOffer.rid7 });
      ridetDetail = data.result;
      toast.success('Données consolidées');
    } catch (err) {
      toast.error(err.message || 'Erreur consolidation Infogreffe');
    } finally {
      isConsolidating = false;
    }
  }

  let isExtractingRidet = $state(false);
  async function extractRidetPdf() {
    if (!selectedOffer || !selectedOffer.rid7) return;
    isExtractingRidet = true;
    try {
      const data = await callAction('extractRidetPdf', { rid7: selectedOffer.rid7 });
      ridetDetail = data.result;
      toast.success('Données RIDET extraites (PDF)');
    } catch (err) {
      toast.error(err.message || 'Erreur extraction PDF RIDET');
    } finally {
      isExtractingRidet = false;
    }
  }

  // ── Recherche intelligente RIDET ──────────────────────────────────────────────
  let fuzzyResults = $state([]);
  let showFuzzyDialog = $state(false);
  let matchingQuery = $state('');

  async function startRidetMatch() {
    if (!selectedOffer || !selectedOffer.company_name) return;
    matchingQuery = selectedOffer.company_name;
    try {
      const data = await callAction('matchRidet', { q: matchingQuery });
      const res = data.result;
      if (res.match_type === 'exact_single') {
        const rid7 = res.results[0].rid7;
        toast.success(`Match trouvé : ${rid7}`);
        await updateOfferRID7(rid7);
      } else if (res.match_type === 'none') {
        toast.error('Aucun établissement trouvé dans le RIDET.');
      } else {
        fuzzyResults = res.results;
        showFuzzyDialog = true;
      }
    } catch (err) {
      toast.error('Erreur lors de la recherche RIDET');
    }
  }
</script>

<svelte:head><title>Offres d'emploi — Intelligence</title></svelte:head>

<!-- En-tête -->
<div class="border-b px-6 py-4">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-xl font-semibold">Offres d'emploi</h1>
      <p class="text-muted-foreground mt-0.5 text-sm">
        {data.pagination.total} offre{data.pagination.total !== 1 ? 's' : ''}
        {activeFiltersCount > 0 ? `· ${activeFiltersCount} filtre${activeFiltersCount > 1 ? 's' : ''} actif${activeFiltersCount > 1 ? 's' : ''}` : ''}
      </p>
    </div>
    <DropdownMenu.Root>
      <DropdownMenu.Trigger>
        {#snippet child({ props })}
          <Button {...props} variant="outline" size="sm" class="gap-2" disabled={isSyncing}>
            <RefreshCw class="size-4 {isSyncing ? 'animate-spin' : ''}" strokeWidth={1.75} />
            Synchroniser
          </Button>
        {/snippet}
      </DropdownMenu.Trigger>
      <DropdownMenu.Content align="end">
        <DropdownMenu.Item onclick={() => triggerSync(null)}>Toutes les sources</DropdownMenu.Item>
        <DropdownMenu.Separator />
        {#each SOURCES.slice(1) as src}
          <DropdownMenu.Item onclick={() => triggerSync([src.value])}>{src.label}</DropdownMenu.Item>
        {/each}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  </div>

  <!-- Filtres -->
  <div class="mt-3 flex flex-wrap items-center gap-2">
    <div class="relative">
      <Search class="text-muted-foreground absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" strokeWidth={1.75} />
      <input
        type="text"
        placeholder="Rechercher…"
        bind:value={searchInput}
        onkeydown={(e) => e.key === 'Enter' && applyFilters()}
        class="border-input bg-background h-8 rounded-md border pl-8 pr-3 text-sm focus:outline-none focus:ring-1"
      />
    </div>
    <select bind:value={sourceFilter} onchange={applyFilters}
      class="border-input bg-background h-8 rounded-md border px-2 text-sm focus:outline-none">
      {#each SOURCES as s}<option value={s.value}>{s.label}</option>{/each}
    </select>
    <select bind:value={statusFilter} onchange={applyFilters}
      class="border-input bg-background h-8 rounded-md border px-2 text-sm focus:outline-none">
      {#each STATUSES as s}<option value={s.value}>{s.label}</option>{/each}
    </select>
    {#if activeFiltersCount > 0}
      <Button variant="ghost" size="sm" class="h-8 gap-1 text-xs" onclick={clearFilters}>
        <X class="size-3" />Effacer
      </Button>
    {/if}
  </div>
</div>

<!-- Tableau -->
<div class="flex-1 overflow-auto">
  {#if data.offers.length === 0}
    <div class="text-muted-foreground flex flex-col items-center justify-center py-20 gap-3">
      <Search class="size-10 opacity-30" strokeWidth={1} />
      <p class="text-sm">Aucune offre trouvée</p>
      {#if activeFiltersCount > 0}
        <Button variant="outline" size="sm" onclick={clearFilters}>Effacer les filtres</Button>
      {/if}
    </div>
  {:else}
    <table class="w-full text-sm">
      <thead class="bg-muted/40 border-b">
        <tr>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Titre</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Entreprise</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Source</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Contrat</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Statut</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Score</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Éval.</th>
          <th class="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Publiée</th>
          <th class="px-4 py-2.5"></th>
        </tr>
      </thead>
      <tbody class="divide-y">
        {#each data.offers as offer}
          <tr class="hover:bg-muted/30 cursor-pointer transition-colors" onclick={() => openOffer(offer)}>
            <td class="max-w-xs px-4 py-3"><span class="line-clamp-1 font-medium">{offer.title}</span></td>
            <td class="px-4 py-3">
              <span class="text-muted-foreground line-clamp-1">{offer.company_name || '—'}</span>
              {#if offer.rid7}<span class="text-muted-foreground/60 block text-[10px]">{offer.rid7}</span>{/if}
            </td>
            <td class="px-4 py-3">
              <span class="rounded-full px-2 py-0.5 text-[11px] font-medium {SOURCE_COLORS[offer.source] || ''}">
                {offer.source}
              </span>
            </td>
            <td class="px-4 py-3 text-muted-foreground">{offer.contract_type || '—'}</td>
            <td class="px-4 py-3">
              <span class="rounded-full px-2 py-0.5 text-[11px] font-medium {STATUS_COLORS[offer.status] || ''}">
                {offer.status}
              </span>
            </td>
            <td class="px-4 py-3">
              <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums {scoreColor(offer.score)}">
                {offer.score}
              </span>
            </td>
            <td class="px-4 py-3">
              {#if offer.eval_category}
                <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold {EVAL_COLORS[offer.eval_category] || ''}">
                  {EVAL_LABELS[offer.eval_category] || offer.eval_category}
                </span>
              {:else}
                <span class="text-muted-foreground/40 text-[11px]">—</span>
              {/if}
            </td>
            <td class="px-4 py-3 text-muted-foreground tabular-nums">{formatDate(offer.date_published)}</td>
            <td class="px-4 py-3">
              {#if offer.url_external}
                <a href={offer.url_external} target="_blank" rel="noopener noreferrer"
                  onclick={(e) => e.stopPropagation()}
                  class="text-muted-foreground hover:text-foreground">
                  <ExternalLink class="size-3.5" strokeWidth={1.75} />
                </a>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<!-- Pagination -->
{#if data.pagination.totalPages > 1}
  <div class="border-t px-4 py-3 flex items-center justify-between text-sm">
    <span class="text-muted-foreground text-xs">
      Page {data.pagination.page} / {data.pagination.totalPages} · {data.pagination.total} résultats
    </span>
    <div class="flex items-center gap-1">
      <Button variant="outline" size="sm" disabled={data.pagination.page <= 1} onclick={() => changePage(data.pagination.page - 1)}>
        <ChevronLeft class="size-4" />
      </Button>
      <Button variant="outline" size="sm" disabled={data.pagination.page >= data.pagination.totalPages} onclick={() => changePage(data.pagination.page + 1)}>
        <ChevronRight class="size-4" />
      </Button>
    </div>
  </div>
{/if}

<!-- ── Drawer détail offre ──────────────────────────────────────────────────── -->
{#if drawerOpen && selectedOffer}
  <div class="fixed inset-0 z-40 bg-black/20" onclick={closeDrawer} role="presentation"></div>

  <div class="fixed top-0 right-0 z-50 flex h-full w-[520px] flex-col border-l bg-background shadow-xl">

    <!-- Header -->
    <div class="flex items-start justify-between border-b px-5 py-4">
      <div class="min-w-0 pr-4">
        <h2 class="truncate font-semibold">{selectedOffer.title}</h2>
        <div class="mt-0.5 flex items-center gap-2 flex-wrap">
          {#if selectedOffer.rid7}
            <a
              href="/job-intel/ridet?q={selectedOffer.rid7}"
              class="text-sm font-medium text-primary hover:underline"
              title="Ouvrir la fiche RIDET"
            >{selectedOffer.company_name || '—'}</a>
            <span class="font-mono text-[11px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{selectedOffer.rid7}</span>
          {:else}
            <span class="text-sm text-muted-foreground">{selectedOffer.company_name || '—'}</span>
          {/if}
          {#if selectedOffer.url_external}
            <a href={selectedOffer.url_external} target="_blank" rel="noopener noreferrer"
               class="text-muted-foreground hover:text-foreground" title="Voir l'offre originale">
              <ExternalLink class="size-3.5" />
            </a>
          {/if}
        </div>
      </div>
      <Button variant="ghost" size="sm" onclick={closeDrawer} class="-mr-1 shrink-0">
        <X class="size-4" />
      </Button>
    </div>

    <!-- Onglets -->
    <div class="flex border-b text-sm">
      {#each [['detail','Détail'], ['liaison','Entreprise'], ['edit','Éditer'], ['ia','Actions IA']] as [tab, label]}
        <button
          onclick={() => (drawerTab = tab)}
          class="flex-1 px-3 py-2.5 font-medium transition-colors
            {drawerTab === tab
              ? 'border-b-2 border-[var(--color-primary-default)] text-[var(--color-primary-default)]'
              : 'text-muted-foreground hover:text-foreground'}"
        >{label}</button>
      {/each}
    </div>

    <!-- Corps -->
    <div class="flex-1 overflow-y-auto">

      <!-- ── Onglet Entreprise ── -->
      {#if drawerTab === 'liaison'}
        <div class="px-5 py-4 space-y-6">

          <!-- Navigation rapide -->
          {#if selectedOffer.rid7}
            <div class="flex gap-2 flex-wrap">
              <a
                href="/job-intel/ridet?q={selectedOffer.rid7}"
                class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
              >
                <Building2 class="size-3.5" />
                Fiche RIDET
              </a>
              <a
                href="/job-intel/offers?rid7={selectedOffer.rid7}"
                onclick={closeDrawer}
                class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
              >
                <Search class="size-3.5" />
                Toutes les offres
              </a>
            </div>
          {/if}

          <!-- Recherche Automatique (Matching) -->
          <div class="flex items-center justify-between gap-4 p-3 rounded-lg border bg-primary/5">
            <div class="flex items-center gap-3">
              <Sparkles class="size-5 text-primary" />
              <span class="text-sm font-medium">Recherche intelligente RIDET</span>
            </div>
            <Button size="sm" class="gap-2 font-bold" onclick={startRidetMatch}>
              <Search class="size-4" />
              Rechercher RIDET
            </Button>
          </div>

          <!-- RID7 Actuel & Consolidation -->
          <div class="space-y-3">
            <p class="text-muted-foreground text-xs font-medium uppercase tracking-wide">Identification RIDET</p>
            <div class="flex items-center gap-3">
              <div class="flex-1 font-mono text-sm bg-muted/50 p-2.5 rounded border border-dashed text-center">
                {selectedOffer.rid7 || 'Aucun RID7'}
              </div>
              {#if selectedOffer.rid7}
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700 h-10 px-3" onclick={() => updateOfferRID7('')}>
                  <X class="size-4" />
                </Button>
              {/if}
            </div>

            {#if selectedOffer.rid7}
              <Button
                variant="secondary"
                class="w-full gap-2 border-2 border-green-200 bg-green-50 text-green-700 hover:bg-green-100"
                onclick={extractRidetPdf}
                disabled={isExtractingRidet}
              >
                {#if isExtractingRidet}
                  <Loader2 class="size-4 animate-spin" />
                  Extraction en cours…
                {:else}
                  <Sparkles class="size-4" />
                  Consolider RIDET (PDF)
                {/if}
              </Button>
              <Button
                variant="secondary"
                class="w-full gap-2 border-2 border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                onclick={consolidateRidet}
                disabled={isConsolidating}
              >
                {#if isConsolidating}
                  <Loader2 class="size-4 animate-spin" />
                  Consolidation en cours...
                {:else}
                  <RefreshCw class="size-4" />
                  Consolider (Infogreffe.nc)
                {/if}
              </Button>
            {/if}

            {#if ridetDetail && ridetDetail.dirigeants && ridetDetail.dirigeants.length > 0}
              <div class="mt-4 p-3 bg-blue-50/50 rounded-lg border border-blue-100">
                <p class="text-[10px] font-bold text-blue-700 uppercase tracking-widest mb-2">Dirigeants identifiés</p>
                <div class="space-y-1.5">
                  {#each ridetDetail.dirigeants as dir}
                    <div class="flex items-center gap-2 text-sm font-medium text-slate-700">
                      <Users class="size-3.5 text-blue-500" />
                      {dir}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>

          <div class="flex items-center gap-4">
            <div class="h-px flex-1 bg-border/50"></div>
            <span class="text-[10px] text-muted-foreground uppercase font-bold tracking-widest">Saisie manuelle</span>
            <div class="h-px flex-1 bg-border/50"></div>
          </div>

          <!-- Saisie Manuelle -->
          <div class="flex items-center gap-2">
            <input
              type="text"
              placeholder="Saisir RID7 (7 chiffres)…"
              maxlength="7"
              class="border-input bg-background h-10 flex-1 rounded-md border px-3 text-sm focus:outline-none focus:ring-1"
              id="manual-rid7"
            />
            <Button size="sm" variant="outline" class="h-10" onclick={() => {
              const input = document.getElementById('manual-rid7');
              if (input && input.value.length === 7) updateOfferRID7(input.value);
              else toast.error('Le RID7 doit comporter 7 chiffres');
            }}>
              Assigner
            </Button>
          </div>

          <hr class="opacity-50" />

          <!-- Recherche Manuelle Référentiel -->
          <div>
            <p class="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">Recherche manuelle</p>
            <div class="relative">
              <Search class="text-muted-foreground absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" strokeWidth={1.75} />
              <input
                type="text"
                placeholder="Nom, enseigne ou sigle…"
                bind:value={ridetSearchQuery}
                oninput={searchRidet}
                class="border-input bg-background h-10 w-full rounded-md border pl-8 pr-3 text-sm focus:outline-none focus:ring-1"
              />
              {#if isSearchingRidet}
                <RefreshCw class="text-muted-foreground absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 animate-spin" />
              {/if}
            </div>

            <div class="mt-3 space-y-1 max-h-[250px] overflow-y-auto">
              {#each ridetSearchResults as entry}
                <button
                  class="w-full text-left p-3 rounded-lg border hover:bg-muted/50 transition-colors group"
                  onclick={() => updateOfferRID7(entry.rid7)}
                >
                  <div class="flex items-center justify-between">
                    <span class="font-semibold text-sm line-clamp-1">{entry.denomination || entry.enseigne}</span>
                    <span class="font-mono text-[11px] text-muted-foreground bg-muted px-1.5 rounded">{entry.rid7}</span>
                  </div>
                  <div class="flex items-center gap-2 mt-1 text-[11px] text-muted-foreground">
                    <Building class="size-3" />
                    <span>{entry.commune} · {entry.forme_juridique}</span>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        </div>
      {/if}

      <!-- ── Onglet Détail ── -->
      {#if drawerTab === 'detail'}
        <div class="px-5 py-4 space-y-5">
          <!-- ... (Infos de l'offre déjà existantes) ... -->
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p class="text-muted-foreground text-xs">Source</p>
              <span class="mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium {SOURCE_COLORS[selectedOffer.source] || ''}">
                {selectedOffer.source}
              </span>
            </div>
            <div>
              <p class="text-muted-foreground text-xs">Statut</p>
              <span class="mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium {STATUS_COLORS[selectedOffer.status] || ''}">
                {selectedOffer.status}
              </span>
            </div>
            <div>
              <p class="text-muted-foreground text-xs">Contrat</p>
              <p class="mt-0.5 font-medium">{selectedOffer.contract_type || '—'}</p>
            </div>
            <div>
              <p class="text-muted-foreground text-xs">Score priorité</p>
              <span class="mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold {scoreColor(selectedOffer.score)}">
                {selectedOffer.score} / 100
              </span>
            </div>
            <div>
              <p class="text-muted-foreground text-xs">Localisation</p>
              <p class="mt-0.5">{selectedOffer.location || '—'}</p>
            </div>
            <div>
              <p class="text-muted-foreground text-xs">Publiée le</p>
              <p class="mt-0.5">{formatDate(selectedOffer.date_published)}</p>
            </div>
          </div>

          {#if selectedOffer.description}
            <div>
              <p class="text-muted-foreground mb-1.5 text-xs font-medium uppercase tracking-wide">Description</p>
              <p class="text-sm leading-relaxed whitespace-pre-line">{selectedOffer.description}</p>
            </div>
          {/if}

          <!-- Données Consolidées RIDET (Dirigeants, etc.) -->
          {#if ridetDetail}
            <div class="rounded-xl border border-blue-100 bg-blue-50/20 p-4 space-y-4">
              <div class="flex items-center justify-between">
                <p class="text-xs font-bold uppercase tracking-widest text-blue-700">Données Consolidées</p>
                <Badge variant="outline" class="bg-blue-100 text-blue-700 border-blue-200">Infogreffe.nc</Badge>
              </div>
              
              {#if ridetDetail.adresse}
                <div>
                  <p class="text-[10px] text-muted-foreground uppercase font-medium">Adresse Siège</p>
                  <p class="text-sm mt-0.5 italic">{ridetDetail.adresse}</p>
                </div>
              {/if}

              {#if ridetDetail.code_naf}
                <div>
                  <p class="text-[10px] text-muted-foreground uppercase font-medium">Activité (NAF)</p>
                  <p class="text-sm mt-0.5 font-medium">{ridetDetail.code_naf} - {ridetDetail.activite_principale}</p>
                </div>
              {/if}

              {#if ridetDetail.dirigeants && ridetDetail.dirigeants.length > 0}
                <div>
                  <p class="text-[10px] text-muted-foreground uppercase font-medium">Dirigeants & Représentants</p>
                  <div class="mt-2 space-y-1">
                    {#each ridetDetail.dirigeants as dir}
                      <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
                        <Users class="size-3.5 text-blue-500" />
                        {dir}
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/if}

          <!-- Action commerciale -->
          {#if selectedOffer.rid7}
            <div class="space-y-3">

              {#if actionResult}
                <!-- ── Résultat de l'action ────────────────────────────────── -->

                <!-- Catégorie évaluation -->
                <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-800 dark:bg-amber-900/20">
                  <p class="text-[10px] font-bold uppercase tracking-widest text-amber-700 dark:text-amber-400 mb-1">Catégorie évaluation</p>
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-mono text-xs font-bold text-amber-800 dark:text-amber-300 bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5 rounded">
                      {actionResult.eval_category.code}
                    </span>
                    <span class="text-sm text-amber-700 dark:text-amber-400">{actionResult.eval_category.label}</span>
                  </div>
                  {#if actionResult.product}
                    <p class="text-xs text-amber-600 dark:text-amber-500 mt-1.5">
                      Produit : {actionResult.product.name}
                      — {Number(actionResult.product.price).toLocaleString('fr-FR')} {actionResult.product.currency}
                    </p>
                  {/if}
                </div>

                <!-- Compte + Contacts -->
                <div class="flex items-center gap-1.5 flex-wrap">
                  <a
                    href="/accounts/{actionResult.account.id}"
                    class="inline-flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-100 transition-colors dark:border-green-800 dark:bg-green-900/20 dark:text-green-400"
                  >
                    <Building2 class="size-3.5" strokeWidth={1.75} />
                    {actionResult.account.name}
                    {#if actionResult.account.created}
                      <span class="text-[10px] font-normal opacity-70">nouveau</span>
                    {/if}
                    <ExternalLink class="size-3" />
                  </a>
                  {#each actionResult.contacts as c}
                    <a
                      href="/contacts/{c.id}"
                      class="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-400"
                    >
                      {c.name}{c.title ? ` · ${c.title}` : ''}
                    </a>
                  {/each}
                </div>

                <!-- Générer l'email + Créer l'opportunité -->
                {#if !showProspectForm}
                  <div class="flex items-center gap-2 flex-wrap">
                    <button
                      onclick={() => runAI('email-job').then(() => openProspectForm())}
                      disabled={!!runningAction}
                      class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
                    >
                      {#if runningAction === 'email-job'}
                        <Loader2 class="size-3.5 animate-spin" />
                        Génération…
                      {:else}
                        <Mail class="size-3.5" strokeWidth={1.75} />
                        Générer l'email
                      {/if}
                    </button>
                    <button
                      onclick={openProspectForm}
                      class="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/5 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/10 transition-colors"
                    >
                      <Zap class="size-3.5" strokeWidth={1.75} />
                      Créer l'opportunité
                    </button>
                  </div>
                {:else}
                  <div class="rounded-lg border bg-muted/30 p-4 space-y-3">
                    <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Nouvelle opportunité — {actionResult.account.name}
                    </p>

                    <div>
                      <label class="text-xs text-muted-foreground" for="prospect-name">Nom de l'opportunité</label>
                      <input
                        id="prospect-name"
                        type="text"
                        bind:value={prospectName}
                        class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1"
                      />
                    </div>

                    <div>
                      <label class="text-xs text-muted-foreground" for="prospect-email">
                        Email / Notes
                        {#if offerAnalyses.find(a => a.analysis_type === 'email_job')}
                          <span class="text-primary ml-1">· pré-rempli depuis l'analyse IA</span>
                        {/if}
                      </label>
                      <textarea
                        id="prospect-email"
                        bind:value={prospectEmailDraft}
                        rows="8"
                        class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 resize-y font-mono leading-relaxed"
                      ></textarea>
                    </div>

                    <div class="flex items-center gap-2 pt-1">
                      <button
                        onclick={createProspect}
                        disabled={prospectCreating || !prospectName.trim()}
                        class="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                      >
                        {#if prospectCreating}
                          <Loader2 class="size-3.5 animate-spin" />
                        {:else}
                          <Zap class="size-3.5" strokeWidth={1.75} />
                        {/if}
                        Confirmer
                      </button>
                      <button
                        onclick={() => (showProspectForm = false)}
                        class="text-sm text-muted-foreground hover:text-foreground"
                      >Annuler</button>
                    </div>
                  </div>
                {/if}

              {:else}
                <!-- ── Avant l'action ─────────────────────────────────────── -->
                <div class="flex items-center gap-2 flex-wrap">
                  {#if crmAccount}
                    <a
                      href="/accounts/{crmAccount.id}"
                      class="inline-flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-100 transition-colors dark:border-green-800 dark:bg-green-900/20 dark:text-green-400"
                    >
                      <Building2 class="size-3.5" strokeWidth={1.75} />
                      {crmAccount.name}
                      <ExternalLink class="size-3" />
                    </a>
                  {/if}
                  <button
                    onclick={startAction}
                    disabled={actionLoading}
                    class="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/5 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/10 transition-colors disabled:opacity-50"
                  >
                    {#if actionLoading}
                      <Loader2 class="size-3.5 animate-spin" />
                      Classification en cours…
                    {:else}
                      <Zap class="size-3.5" strokeWidth={1.75} />
                      Créer action commerciale
                    {/if}
                  </button>
                </div>
              {/if}

            </div>
          {/if}

          <!-- Analyses existantes -->
          <div>
            <p class="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">
              Analyses IA enregistrées
              {#if offerAnalyses.length > 0}
                <span class="normal-case font-normal">({offerAnalyses.length})</span>
              {/if}
            </p>
            {#if loadingAnalyses}
              <p class="text-muted-foreground text-sm">Chargement…</p>
            {:else if offerAnalyses.length === 0}
              <p class="text-muted-foreground text-sm">Aucune analyse — utilisez l'onglet "Actions IA"</p>
            {:else}
              <div class="space-y-2">
                {#each offerAnalyses as analysis (analysis.id)}
                  {@const isSkill = analysis.analysis_type === 'skill_analysis'}
                  {@const skills = isSkill ? (() => { try { const d = typeof analysis.result_json === 'object' ? analysis.result_json : JSON.parse(analysis.result_text); return d?.critical_skills || []; } catch { return []; } })() : []}
                  {@const text = analysis.result_text || ''}
                  {@const copyText = isSkill ? skills.map(s => `${s.skill}\n→ ${s.reason}\n💼 ${s.sales_hook}`).join('\n\n') : text}
                  {@const expanded = expandedAnalyses.has(analysis.id)}
                  <div class="rounded-lg border bg-muted/30 overflow-hidden">
                    <!-- En-tête cliquable -->
                    <button
                      onclick={() => toggleAnalysis(analysis.id)}
                      class="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-muted/50 transition-colors"
                    >
                      <span class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                        {analysisTypeLabel(analysis.analysis_type)}
                        <span class="normal-case font-normal opacity-60">· {analysis.model_used} · {formatDate(analysis.created_at)}</span>
                      </span>
                      <svg class="size-3.5 text-muted-foreground shrink-0 transition-transform {expanded ? 'rotate-180' : ''}"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                      </svg>
                    </button>
                    <!-- Contenu dépliable -->
                    {#if expanded}
                      <div class="px-3 pb-3 border-t">
                        {#if isSkill && skills.length > 0}
                          <!-- Rendu structuré pour skill_analysis -->
                          <div class="mt-2 space-y-3">
                            {#each skills as s, i}
                              <div class="rounded-md border bg-background px-3 py-2.5">
                                <p class="font-medium text-sm">{i + 1}. {s.skill}</p>
                                <p class="mt-1 text-xs text-muted-foreground leading-relaxed">{s.reason}</p>
                                <p class="mt-1.5 text-xs text-blue-600 dark:text-blue-400 leading-relaxed">💼 {s.sales_hook}</p>
                              </div>
                            {/each}
                          </div>
                        {:else}
                          <p class="mt-2 text-sm leading-relaxed whitespace-pre-wrap">{text}</p>
                        {/if}
                        <div class="mt-2 flex items-center justify-between">
                          <button
                            onclick={() => { navigator.clipboard.writeText(copyText); toast.success('Copié'); }}
                            class="text-xs text-muted-foreground hover:text-foreground underline"
                          >Copier</button>
                          <button
                            onclick={() => deleteAnalysis(analysis.id)}
                            class="text-xs text-red-500 hover:text-red-700 underline"
                          >Supprimer</button>
                        </div>
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>

      <!-- ── Onglet Édition Offre ── -->
      {:else if drawerTab === 'edit'}
        <div class="px-5 py-4 space-y-4">
          <div>
            <label class="text-xs font-medium text-muted-foreground">Titre</label>
            <input type="text" bind:value={editData.title}
              class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs font-medium text-muted-foreground">Localisation</label>
              <input type="text" bind:value={editData.location}
                class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1" />
            </div>
            <div>
              <label class="text-xs font-medium text-muted-foreground">Contrat</label>
              <select bind:value={editData.contract_type}
                class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none">
                <option value="">—</option>
                {#each CONTRACT_TYPES as ct}<option value={ct}>{ct}</option>{/each}
              </select>
            </div>
            <div>
              <label class="text-xs font-medium text-muted-foreground">Expérience requise</label>
              <input type="text" bind:value={editData.experience_req}
                class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1" />
            </div>
            <div>
              <label class="text-xs font-medium text-muted-foreground">Nb postes</label>
              <input type="number" min="1" bind:value={editData.nb_postes}
                class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1" />
            </div>
            <div>
              <label class="text-xs font-medium text-muted-foreground">Score (0-100)</label>
              <input type="number" min="0" max="100" bind:value={editData.score}
                class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1" />
            </div>
            <div>
              <label class="text-xs font-medium text-muted-foreground">Statut</label>
              <select bind:value={editData.status}
                class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none">
                {#each STATUSES.slice(1) as s}<option value={s.value}>{s.label}</option>{/each}
              </select>
            </div>
          </div>
          <div>
            <label class="text-xs font-medium text-muted-foreground">Formation requise</label>
            <textarea rows="2" bind:value={editData.education_req}
              class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 resize-none"></textarea>
          </div>
          <div>
            <label class="text-xs font-medium text-muted-foreground">Description</label>
            <textarea rows="6" bind:value={editData.description}
              class="border-input bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 resize-none"></textarea>
          </div>
        </div>

      <!-- ── Onglet Actions IA ── -->
      {:else if drawerTab === 'ia'}
        <div class="px-5 py-4 space-y-5">

          <!-- Actions sur l'offre -->
          <div>
            <p class="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">
              <Zap class="inline size-3 mr-1" strokeWidth={1.75} />Offre
            </p>
            <div class="flex flex-wrap gap-2">
              {#each AI_ACTIONS as action}
                <button
                  onclick={() => runAI(action.key)}
                  disabled={!!runningAction}
                  class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium
                    transition-colors hover:bg-muted disabled:opacity-50
                    {iaOutputType === action.type ? 'border-[var(--color-primary-default)] text-[var(--color-primary-default)]' : ''}"
                >
                  {#if runningAction === action.key}
                    <Loader2 
 class="size-3 animate-spin" />
                  {:else}
                    <action.icon class="size-3" strokeWidth={1.75} />
                  {/if}
                  {action.label}
                </button>
              {/each}
            </div>
          </div>

          <!-- Actions sur l'entreprise (nécessite rid7) -->
          {#if selectedOffer.rid7}
            <div>
              <p class="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">
                <Zap class="inline size-3 mr-1" strokeWidth={1.75} />Entreprise ({selectedOffer.rid7})
              </p>
              <div class="flex flex-wrap gap-2">
                {#each COMPANY_AI_ACTIONS as action}
                  <button
                    onclick={() => runAI(action.key, true)}
                    disabled={!!runningAction}
                    class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium
                      transition-colors hover:bg-muted disabled:opacity-50
                      {iaOutputType === action.type ? 'border-[var(--color-primary-default)] text-[var(--color-primary-default)]' : ''}"
                  >
                    {#if runningAction === action.key}
                      <Loader2 
 class="size-3 animate-spin" />
                    {:else}
                      <action.icon class="size-3" strokeWidth={1.75} />
                    {/if}
                    {action.label}
                  </button>
                {/each}
              </div>
            </div>
          {:else}
            <p class="text-muted-foreground text-xs">
              Les actions IA sur l'entreprise nécessitent un RID7 associé à l'offre.
            </p>
          {/if}

          <!-- Résultat -->
          {#if runningAction}
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 
 class="size-4 animate-spin" strokeWidth={1.75} />
              Génération en cours…
            </div>
          {:else if iaOutput}
            <div>
              <p class="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">Résultat</p>
              <div class="rounded-lg border bg-muted/30 px-3 py-3">
                <p class="text-sm leading-relaxed whitespace-pre-wrap">{iaOutput}</p>
              </div>
              <button
                onclick={() => { navigator.clipboard.writeText(iaOutput); toast.success('Copié'); }}
                class="mt-2 text-xs text-muted-foreground hover:text-foreground underline"
              >Copier</button>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="border-t px-5 py-3 flex items-center justify-between gap-2">
      <div>
        {#if selectedOffer.url_external}
          <a href={selectedOffer.url_external} target="_blank" rel="noopener noreferrer"
            class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
            <ExternalLink class="size-3.5" strokeWidth={1.75} />Voir l'offre originale
          </a>
        {/if}
      </div>
      {#if drawerTab === 'edit'}
        <Button size="sm" onclick={saveOffer} disabled={isSavingOffer} class="gap-2">
          {#if isSavingOffer}<Loader2 class="size-3.5 animate-spin" />{:else}<Save class="size-3.5" />{/if}
          Enregistrer
        </Button>
      {:else}
        <Button variant="ghost" size="sm" onclick={closeDrawer}>Fermer</Button>
      {/if}
    </div>
  </div>
{/if}

<!-- Formulaire caché sync -->
<form method="POST" action="?/sync" bind:this={syncForm} use:enhance={syncEnhance} class="hidden">
  <input type="hidden" name="sources" value={syncSources} />
</form>

{#if showFuzzyDialog}
  <RidetFuzzyDialog 
    query={matchingQuery} 
    results={fuzzyResults} 
    onSelect={(rid7) => updateOfferRID7(rid7)}
    onClose={() => (showFuzzyDialog = false)}
  />
{/if}
