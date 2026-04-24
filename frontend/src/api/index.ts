/**
 * Re-exports either the real API client or the mock depending on VITE_USE_MOCK.
 * Set VITE_USE_MOCK=true in frontend/.env for local development without a backend.
 * Set VITE_USE_MOCK=false (or use .env.production) to talk to the real API.
 */
import * as mockApi from './mock';
import * as realApi from './client';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';
const api = useMock ? mockApi : realApi;

export const getDrugClasses = api.getDrugClasses;
export const getDrugsByClass = api.getDrugsByClass;
export const getAttributeTypes = api.getAttributeTypes;
export const getDrug = api.getDrug;
export const getTable = api.getTable;

// Write functions always use the real client (mock has no write operations).
export { createSession, submitReview, getQueue } from './client';
