import { error } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ params, locals, cookies }) {
  const org = locals.org;
  if (!org) throw error(401, 'Organization context required');

  try {
    const data = await apiRequest(`/accounts/${params.id}/`, {}, { cookies, org });
    if (data.error) throw error(404, data.errors || 'Account introuvable');
    return { account: data.account_obj, meta: data };
  } catch (err) {
    if (err.status) throw err;
    throw error(500, `Impossible de charger le compte : ${err.message}`);
  }
}
