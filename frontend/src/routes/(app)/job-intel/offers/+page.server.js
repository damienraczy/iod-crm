// [IOD] iod_job_intel — Offres d'emploi
import { error, fail } from '@sveltejs/kit';
import { apiRequest, buildQueryParams, extractPagination } from '$lib/api-helpers.js';

export async function load({ url, cookies }) {
  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = parseInt(url.searchParams.get('limit') || '25');
  const filters = {
    q: url.searchParams.get('q') || '',
    source: url.searchParams.get('source') || '',
    status: url.searchParams.get('status') || '',
    rid7: url.searchParams.get('rid7') || ''
  };

  const params = buildQueryParams({ page, limit, sort: 'date_published', order: 'desc' });
  if (filters.q) params.append('q', filters.q);
  if (filters.source) params.append('source', filters.source);
  if (filters.status) params.append('status', filters.status);
  if (filters.rid7) params.append('rid7', filters.rid7);

  try {
    const response = await apiRequest(`/iod/offers/?${params}`, {}, cookies);
    return {
      offers: response.results || [],
      pagination: extractPagination(response, limit),
      filters
    };
  } catch (err) {
    throw error(500, `Impossible de charger les offres : ${err.message}`);
  }
}

export const actions = {
  sync: async ({ request, cookies }) => {
    try {
      const form = await request.formData();
      const sourcesRaw = form.get('sources');
      const body = sourcesRaw ? { sources: JSON.parse(sourcesRaw) } : {};
      await apiRequest('/iod/sync/trigger/', { method: 'POST', body }, cookies);
      return { success: true };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Récupère le détail complet d'une offre (description, experience_req, etc.)
  getOffer: async ({ request, cookies }) => {
    const form = await request.formData();
    const id = form.get('id');
    try {
      const offer = await apiRequest(`/iod/offers/${id}/`, {}, cookies);
      return { offer };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Mise à jour partielle d'une offre
  patchOffer: async ({ request, cookies }) => {
    const form = await request.formData();
    const id = form.get('id');
    const dataRaw = form.get('data');
    try {
      const updated = await apiRequest(`/iod/offers/${id}/`, {
        method: 'PATCH',
        body: JSON.parse(dataRaw)
      }, cookies);
      return { offer: updated };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Récupère les analyses IA d'une offre
  getAnalyses: async ({ request, cookies }) => {
    const form = await request.formData();
    const id = form.get('id');
    try {
      const result = await apiRequest(`/iod/offers/${id}/analyses/`, {}, cookies);
      return { analyses: result.results || result || [] };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Supprime une analyse IA
  deleteAnalysis: async ({ request, cookies }) => {
    const form = await request.formData();
    const id = form.get('id');
    try {
      await apiRequest(`/iod/analyses/${id}/`, { method: 'DELETE' }, cookies);
      return { deleted: true };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Cherche ou crée un Account CRM depuis un RIDET
  crmAccount: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7   = form.get('rid7');
    const create = form.get('create') === 'true';
    try {
      if (create) {
        const result = await apiRequest(`/iod/ridet/${rid7}/crm-account/`, { method: 'POST' }, cookies);
        return { account: result.account, created: result.created };
      } else {
        const result = await apiRequest(`/iod/ridet/${rid7}/crm-account/`, {}, cookies);
        return { account: result.account, found: result.found };
      }
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Crée une opportunité CRM liée à l'account
  createOpportunity: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const name        = form.get('name');
    const accountId   = form.get('accountId');
    const description = form.get('description') || '';
    const leadSource  = form.get('leadSource') || 'OTHER';
    try {
      const result = await apiRequest('/opportunities/', {
        method: 'POST',
        body: {
          name,
          account: accountId,
          stage: 'PROSPECTING',
          lead_source: leadSource,
          description,
        }
      }, { cookies, org: locals.org });
      return { opportunityId: result?.id || null, success: true };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Lance une action IA (offre ou entreprise)
  runAI: async ({ request, cookies }) => {
    const form = await request.formData();
    const offerId  = form.get('offerId');
    const actionKey = form.get('actionKey');
    const isCompany = form.get('isCompany') === 'true';
    const rid7     = form.get('rid7') || '';
    const bodyRaw  = form.get('body');
    const body     = bodyRaw ? JSON.parse(bodyRaw) : {};

    let endpoint;
    if (isCompany && rid7) {
      endpoint = `/iod/ridet/${rid7}/ai/${actionKey}/`;
    } else {
      endpoint = `/iod/offers/${offerId}/ai-${actionKey}/`;
    }

    try {
      const analysis = await apiRequest(endpoint, { method: 'POST', body }, cookies);
      return { analysis };
    } catch (err) {
      return fail(502, { error: err.message });
    }
  }
};
