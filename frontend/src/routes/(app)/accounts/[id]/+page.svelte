<script>
  import { goto } from '$app/navigation';
  import {
    Building2, MapPin, Phone, Mail, Globe, ChevronLeft,
    Users, Target, CheckSquare, Hash, ExternalLink
  } from '@lucide/svelte';
  import { Button } from '$lib/components/ui/button/index.js';

  /** @type {{ data: import('./$types').PageData }} */
  let { data } = $props();

  const a = data.account;

  function formatDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }

  const opportunities = data.meta?.opportunity_list || [];
  const contacts      = data.meta?.contacts || [];
  const tasks         = data.meta?.tasks || [];
</script>

<svelte:head><title>{a.name} — Compte CRM</title></svelte:head>

<div class="max-w-4xl mx-auto px-6 py-6 space-y-6">

  <!-- Retour + titre -->
  <div class="flex items-center gap-3">
    <Button variant="ghost" size="sm" onclick={() => goto('/accounts')} class="gap-1.5">
      <ChevronLeft class="size-4" />
      Comptes
    </Button>
  </div>

  <!-- Fiche principale -->
  <div class="rounded-xl border bg-card p-6 space-y-5">
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-3">
        <div class="flex size-12 items-center justify-center rounded-xl bg-primary/10">
          <Building2 class="size-6 text-primary" strokeWidth={1.5} />
        </div>
        <div>
          <h1 class="text-xl font-semibold">{a.name}</h1>
          <div class="flex items-center gap-2 mt-0.5">
            {#if a.rid7}
              <span class="inline-flex items-center gap-1 text-xs text-muted-foreground font-mono">
                <Hash class="size-3" />RIDET {a.rid7}
              </span>
            {/if}
            {#if a.industry}
              <span class="text-xs text-muted-foreground">· {a.industry}</span>
            {/if}
            <span class="inline-block rounded-full px-2 py-0.5 text-[11px] font-medium
              {a.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                           : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}">
              {a.is_active ? 'Actif' : 'Inactif'}
            </span>
          </div>
        </div>
      </div>
      <Button variant="outline" size="sm" onclick={() => goto('/accounts')}>
        Modifier
      </Button>
    </div>

    <!-- Coordonnées -->
    <div class="grid grid-cols-2 gap-4 text-sm">
      {#if a.city || a.address_line}
        <div class="flex items-start gap-2">
          <MapPin class="size-4 mt-0.5 text-muted-foreground shrink-0" strokeWidth={1.5} />
          <span>{[a.address_line, a.city, a.state].filter(Boolean).join(', ') || '—'}</span>
        </div>
      {/if}
      {#if a.phone}
        <div class="flex items-center gap-2">
          <Phone class="size-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
          <a href="tel:{a.phone}" class="hover:underline">{a.phone}</a>
        </div>
      {/if}
      {#if a.email}
        <div class="flex items-center gap-2">
          <Mail class="size-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
          <a href="mailto:{a.email}" class="hover:underline">{a.email}</a>
        </div>
      {/if}
      {#if a.website}
        <div class="flex items-center gap-2">
          <Globe class="size-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
          <a href={a.website} target="_blank" rel="noopener" class="hover:underline inline-flex items-center gap-1">
            {a.website.replace(/^https?:\/\//, '')}
            <ExternalLink class="size-3" />
          </a>
        </div>
      {/if}
    </div>

    {#if a.description}
      <div class="rounded-lg bg-muted/40 px-4 py-3 text-sm text-muted-foreground leading-relaxed">
        {a.description}
      </div>
    {/if}
  </div>

  <!-- Opportunités -->
  <div class="rounded-xl border bg-card p-5">
    <h2 class="flex items-center gap-2 text-sm font-semibold mb-3">
      <Target class="size-4 text-muted-foreground" strokeWidth={1.5} />
      Opportunités ({opportunities.length})
    </h2>
    {#if opportunities.length === 0}
      <p class="text-sm text-muted-foreground">Aucune opportunité</p>
    {:else}
      <div class="divide-y">
        {#each opportunities as opp}
          <div class="py-2.5 flex items-center justify-between text-sm">
            <span class="font-medium">{opp.name}</span>
            <div class="flex items-center gap-3 text-muted-foreground">
              <span class="text-xs">{opp.stage}</span>
              {#if opp.amount && parseFloat(opp.amount) > 0}
                <span class="font-medium text-foreground">{parseFloat(opp.amount).toLocaleString('fr-FR')} XPF</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Contacts -->
  <div class="rounded-xl border bg-card p-5">
    <h2 class="flex items-center gap-2 text-sm font-semibold mb-3">
      <Users class="size-4 text-muted-foreground" strokeWidth={1.5} />
      Contacts ({contacts.length})
    </h2>
    {#if contacts.length === 0}
      <p class="text-sm text-muted-foreground">Aucun contact</p>
    {:else}
      <div class="divide-y">
        {#each contacts as c}
          <div class="py-2.5 flex items-center justify-between text-sm">
            <span class="font-medium">{[c.first_name, c.last_name].filter(Boolean).join(' ') || '—'}</span>
            <div class="flex items-center gap-3 text-muted-foreground text-xs">
              {#if c.mobile_number}<span>{c.mobile_number}</span>{/if}
              {#if c.email}<span>{c.email}</span>{/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Tâches -->
  <div class="rounded-xl border bg-card p-5">
    <h2 class="flex items-center gap-2 text-sm font-semibold mb-3">
      <CheckSquare class="size-4 text-muted-foreground" strokeWidth={1.5} />
      Tâches ({tasks.length})
    </h2>
    {#if tasks.length === 0}
      <p class="text-sm text-muted-foreground">Aucune tâche</p>
    {:else}
      <div class="divide-y">
        {#each tasks as t}
          <div class="py-2.5 flex items-center justify-between text-sm">
            <span class="{t.status === 'completed' ? 'line-through text-muted-foreground' : ''}">{t.title}</span>
            <span class="text-xs text-muted-foreground">{formatDate(t.due_date)}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>

</div>
