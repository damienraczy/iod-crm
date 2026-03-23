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

  // Cherche un Account CRM existant pour un RID7 (lecture seule)
  crmAccount: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/crm-account/`, {}, cookies);
      return { account: result.account, found: result.found };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Orchestre l'action commerciale : classify + account + contacts + produit
  startAction: async ({ request, cookies }) => {
    const form = await request.formData();
    const offerId = form.get('offerId');
    try {
      const result = await apiRequest(`/iod/offers/${offerId}/start-action/`, { method: 'POST' }, cookies);
      return { result };
    } catch (err) {
      return fail(502, { error: err.message });
    }
  },

  // Crée une opportunité CRM liée à l'account, avec un line item eval_nX si disponible
  createOpportunity: async ({ request, locals, cookies }) => {
    const form = await request.formData();
    const name        = form.get('name');
    const accountId   = form.get('accountId');
    const description = form.get('description') || '';
    const leadSource  = form.get('leadSource') || 'OTHER';
    const productId   = form.get('productId') || null;
    const productName = form.get('productName') || '';
    const unitPrice   = form.get('unitPrice') || '0';
    try {
      const result = await apiRequest('/opportunities/', {
        method: 'POST',
        body: { name, account: accountId, stage: 'PROSPECTING', lead_source: leadSource, description }
      }, { cookies, org: locals.org });

      const opportunityId = result?.id;

      // Ajouter le line item eval_nX si un produit a été identifié
      if (opportunityId && productId) {
        try {
          await apiRequest(`/opportunities/${opportunityId}/line-items/`, {
            method: 'POST',
            body: { product_id: productId, name: productName, unit_price: unitPrice, quantity: '1' }
          }, { cookies, org: locals.org });
        } catch {
          // Non-bloquant : l'opportunité est créée, le line item est optionnel
        }
      }

      return { opportunityId, success: true };
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
  },

  // Recherche intelligente RIDET (Exact -> Flou)
  matchRidet: async ({ request, cookies }) => {
    const form = await request.formData();
    const q = form.get('q');
    try {
      const result = await apiRequest(`/iod/ridet/match/?q=${encodeURIComponent(q)}`, {}, cookies);
      return { result };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Récupère les données d'un établissement localement
  getRidet: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/`, {}, cookies);
      return { result };
    } catch (err) {
      return fail(404, { error: err.message });
    }
  },

  // Consolide les données RIDET (Scraping Infogreffe)
  consolidateRidet: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/consolidate/`, { method: 'POST' }, cookies);
      return { result };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Extrait les données depuis le PDF avisridet.isee.nc via LLM
  extractRidetPdf: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/extract-ridet/`, { method: 'POST' }, cookies);
      return { result: result.entry };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  }
};
