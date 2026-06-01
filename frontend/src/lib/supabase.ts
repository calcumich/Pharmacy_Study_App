import { createClient } from '@supabase/supabase-js';

const authMode = import.meta.env.VITE_AUTH_MODE ?? 'supabase';
const supabaseOptional = authMode === 'dev' || import.meta.env.VITE_USE_MOCK === 'true';
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? (supabaseOptional ? 'http://localhost:54321' : '');
const supabaseAnonKey = import.meta.env.VITE_PUBLISHABLE_KEY ?? (supabaseOptional ? 'dev-anon-key' : '');

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
