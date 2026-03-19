// [IOD] iod_job_intel — Paramètres AppParameter
import { error, fail } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

export async function load({ cookies }) {
  try {
    const response = await apiRequest('/iod/parameters/', {}, cookies);
    return {
      parameters: response.results || response || []
    };
  } catch (err) {
    throw error(500, `Impossible de charger les paramètres : ${err.message}`);
  }
}

export const actions = {
  update: async ({ request, cookies }) => {
    try {
      const form = await request.formData();
      const key = form.get('key')?.toString();
      const value = form.get('value')?.toString();
      if (!key) return fail(400, { error: 'Clé manquante' });

      await apiRequest(`/iod/parameters/${key}/`, { method: 'PATCH', body: { value } }, cookies);
      return { success: true };
    } catch (err) {
      return fail(400, { error: err.message });
    }
  }
};
