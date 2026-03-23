import { error, fail } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ url, cookies }) {
  const q = url.searchParams.get('q') || '';

  try {
    const paramsResp = await apiRequest('/iod/parameters/', {}, cookies);
    const params = Array.isArray(paramsResp) ? paramsResp : [];

    const status     = params.find((p) => p.key === 'ridet_import_status')?.value || 'IDLE';
    const progress   = parseInt(params.find((p) => p.key === 'ridet_import_progress')?.value || '0');
    const lastImport = params.find((p) => p.key === 'ridet_last_import')?.value || null;
    const lastError  = params.find((p) => p.key === 'ridet_import_error')?.value || '';

    // Recherche d'établissements si une requête est fournie
    let entries = [];
    if (q.trim().length >= 2) {
      try {
        const res = await apiRequest(`/iod/ridet/search/?q=${encodeURIComponent(q)}`, {}, cookies);
        entries = Array.isArray(res) ? res : [];
      } catch { entries = []; }
    }

    return { ridet: { status, progress, lastImport, lastError }, entries, q };
  } catch (err) {
    console.error('Error loading RIDET:', err);
    return { ridet: { status: 'IDLE', progress: 0, lastImport: null, lastError: '' }, entries: [], q };
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  refresh: async ({ cookies }) => {
    try {
      await apiRequest('/iod/ridet/refresh/', { method: 'POST' }, cookies);
      return { success: true };
    } catch (err) {
      return fail(400, { error: err.message || 'Erreur lors du lancement de la mise à jour' });
    }
  },

  // Récupère le détail complet d'un établissement (pour le panneau latéral)
  getEntry: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/`, {}, cookies);
      return { entry: result };
    } catch (err) {
      return fail(404, { error: err.message });
    }
  },

  // Extrait les données depuis le PDF avisridet.isee.nc via LLM
  extractRidet: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/extract-ridet/`, { method: 'POST' }, cookies);
      return { entry: result.entry };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Consolide les données depuis Infogreffe.nc (scraping)
  consolidate: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7 = form.get('rid7');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/consolidate/`, { method: 'POST' }, cookies);
      return { entry: result.entry ?? result };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },

  // Met à jour la description éditoriale (seul champ modifiable)
  saveDescription: async ({ request, cookies }) => {
    const form = await request.formData();
    const rid7        = form.get('rid7');
    const description = form.get('description');
    try {
      const result = await apiRequest(`/iod/ridet/${rid7}/`, {
        method: 'PATCH',
        body: { description }
      }, cookies);
      return { entry: result };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  },
};
