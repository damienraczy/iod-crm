### pays
dans `backend/common/utils.py`
COUNTRIES = (
	("NC", _("New Caledonia")),

dans `/frontend/src/routes/(app)/settings/organization/+page.svelte`
const countryOptions = [
	{ value: '', label: 'Select Country', flag: '🇫🇷' },


dans `/frontend/src/lib/constants/filters.js` 

export const CURRENCY_CODES = [
	{ value: 'XPF', label: 'XPF - Franc' },
	...

export const CURRENCY_SYMBOLS = {
	XPF: 'F',
	...

### devises
dans `backend/common/utils.py`

CURRENCY_CODES = (
	("XPF", _("XPF, Franc")),

CURRENCY_SYMBOLS = {
	"XPF": "F",

dans `frontend/src/lib/utils/formatting.js`, ligne 65
Mettre currency à XPF
- export function formatCurrency(amount, currency = 'XPF', compact = false) {
remplacer `en-US` en `fr-FR` dans intl:
- Intl.DateTimeFormat(
- Intl.NumberFormat(
remplacer `en-US` en `fr-FR` dans intl:
- dans `frontend/src/routes/(app)/accounts/[id]/+page.svelte`
- dans `frontend/src/routes/(app)/job-intel/offers/+page.svelte`
- dans `frontend/src/routes/(app)/settings/organization/+page.svelte`
