import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';

/** @type {import('./$types').PageServerLoad} */
export async function load({ fetch }) {
  try {
    const paramsResp = await fetch(`${env.PUBLIC_API_URL}/api/iod/parameters/`);
    if (!paramsResp.ok) throw error(paramsResp.status, 'Erreur lors de la récupération des paramètres');
    
    const params = await paramsResp.json();
    
    const status = params.find((p) => p.key === 'ridet_import_status')?.value || 'IDLE';
    const progress = parseInt(params.find((p) => p.key === 'ridet_import_progress')?.value || '0');
    const lastImport = params.find((p) => p.key === 'ridet_last_import')?.value || null;
    const lastError = params.find((p) => p.key === 'ridet_import_error')?.value || '';

    return {
      ridet: {
        status,
        progress,
        lastImport,
        lastError
      }
    };
  } catch (err) {
    console.error('Error loading RIDET status:', err);
    return {
      ridet: { status: 'IDLE', progress: 0, lastImport: null, lastError: 'Impossible de joindre le serveur' }
    };
  }
}

/** @type {import('./$types').Actions} */
export const actions = {
  refresh: async ({ fetch }) => {
    try {
      const resp = await fetch(`${env.PUBLIC_API_URL}/api/iod/ridet/refresh/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!resp.ok) {
        const err = await resp.json();
        return { success: false, error: err.detail || 'Erreur lors du lancement de la mise à jour' };
      }
      
      return { success: true };
    } catch (err) {
      return { success: false, error: 'Erreur de connexion au serveur API' };
    }
  }
};
