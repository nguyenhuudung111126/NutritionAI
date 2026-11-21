const rawApiUrl = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '');
const API_BASE = rawApiUrl ? `${rawApiUrl}/api` : '/api';
const TOKEN_KEY = 'nutriguard_token';

const _GET_CACHE = new Map();
const _IN_FLIGHT = new Map();
const CACHE_TTL_MS = 60_000;

export function clearApiCache() {
  _GET_CACHE.clear();
  _IN_FLIGHT.clear();
}

let unauthorizedHandler = null;

export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn;
}

export function getAuthToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setAuthToken(token) {
  clearApiCache();
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors
  }
}

async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const isCacheableGet =
    method === 'GET' && !path.startsWith('/auth/me') && !path.startsWith('/observability') && !path.startsWith('/health');

  if (isCacheableGet) {
    const cached = _GET_CACHE.get(path);
    if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
      return cached.data;
    }
    if (_IN_FLIGHT.has(path)) {
      return _IN_FLIGHT.get(path);
    }
  }

  const runFetch = async () => {
    const token = getAuthToken();
    const headers = { ...(options.headers || {}) };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!res.ok) {
      let msg = `Lỗi HTTP ${res.status}`;
      try {
        const rawText = await res.text();
        try {
          const data = JSON.parse(rawText);
          msg = data.detail || JSON.stringify(data);
        } catch {
          if (rawText) msg = rawText.slice(0, 220);
        }
      } catch {
        // ignore read error
      }
      if (res.status === 401 && !path.startsWith('/auth/login')) {
        setAuthToken('');
        if (unauthorizedHandler) unauthorizedHandler();
      }
      throw new Error(msg);
    }
    const data = await res.json();
    if (isCacheableGet) {
      _GET_CACHE.set(path, { data, ts: Date.now() });
    } else if (method !== 'GET') {
      clearApiCache();
    }
    return data;
  };

  if (isCacheableGet) {
    const p = runFetch().finally(() => _IN_FLIGHT.delete(path));
    _IN_FLIGHT.set(path, p);
    return p;
  }
  return runFetch();
}

export const api = {
  health: () => request('/health'),

  // Auth
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),
  me: () => request('/auth/me'),
  changePassword: (oldPassword, newPassword) =>
    request('/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),

  // Patients (role-scoped)
  getPatients: () => request('/patients'),
  createPatient: (body) =>
    request('/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  deletePatient: (id) => request(`/patients/${id}`, { method: 'DELETE' }),
  updatePatient: (id, body) =>
    request(`/patients/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  getOverview: (id) => request(`/patients/${id}/overview`),
  getTrends: (id) => request(`/patients/${id}/trends`),
  getMealPlans: (id) => request(`/patients/${id}/meal-plans`),
  generateMealPlan: (id, body) =>
    request(`/patients/${id}/meal-plans`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  chat: (id, query) =>
    request(`/patients/${id}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    }),
  uploadCheckup: (id, fileOrFiles, checkupDate) => {
    const fd = new FormData();
    const list = Array.isArray(fileOrFiles) ? fileOrFiles : fileOrFiles ? [fileOrFiles] : [];
    list.forEach((f) => fd.append('files', f));
    if (checkupDate) fd.append('checkup_date', checkupDate);
    return request(`/patients/${id}/checkups/upload`, { method: 'POST', body: fd });
  },
  deleteCheckup: (id, checkupId) =>
    request(`/patients/${id}/checkups/${checkupId}`, { method: 'DELETE' }),

  // Foods
  getFoods: ({ q = '', patientId = '', lowGi = false, lowPotassium = false, lowSodium = false } = {}) => {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (patientId) params.set('patient_id', patientId);
    if (lowGi) params.set('low_gi', 'true');
    if (lowPotassium) params.set('low_potassium', 'true');
    if (lowSodium) params.set('low_sodium', 'true');
    return request(`/foods?${params.toString()}`);
  },
  analyzeDish: ({ dishQuery = '', file = null, patientId = '' } = {}) => {
    const fd = new FormData();
    if (dishQuery) fd.append('dish_query', dishQuery);
    if (patientId) fd.append('patient_id', patientId);
    if (file) fd.append('file', file);
    return request('/foods/analyze', { method: 'POST', body: fd });
  },

  // Admin Management
  adminGetOverview: () => request('/admin/overview'),
  adminGetCatalog: () => request('/admin/catalog'),
  adminToggleCondition: (code) => request(`/admin/conditions/${code}/toggle`, { method: 'PATCH' }),
  adminCreateFood: (body) =>
    request('/admin/foods', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  adminUpdateFood: (foodId, body) =>
    request(`/admin/foods/${foodId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  adminDeleteFood: (foodId) => request(`/admin/foods/${foodId}`, { method: 'DELETE' }),
  adminGetPatients: () => request('/admin/patients'),
  adminUpsertPatientAccount: (patientId, body) =>
    request(`/admin/patients/${patientId}/account`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  adminGetUsers: () => request('/admin/users'),
  adminCreateUser: (body) =>
    request('/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  adminUpdateUser: (userId, body) =>
    request(`/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  adminDeleteUser: (userId) => request(`/admin/users/${userId}`, { method: 'DELETE' }),

  // System / RAG / Evals (Admin only)
  getObservability: () => request('/observability'),
  runEvals: (includeE2e = false) =>
    request('/evals/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ include_e2e: includeE2e }),
    }),
  getRagDocuments: () => request('/rag/documents'),
  uploadRagDocuments: (files, meta) => {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    fd.append('source', meta.source);
    fd.append('group_name', meta.group_name);
    fd.append('published_year', String(meta.published_year));
    fd.append('max_chars', String(meta.max_chars));
    fd.append('overlap', String(meta.overlap));
    return request('/rag/documents', { method: 'POST', body: fd });
  },
  deleteRagDocument: (docId) => request(`/rag/documents/${docId}`, { method: 'DELETE' }),
  searchRag: (q) => request(`/rag/search?q=${encodeURIComponent(q)}&top_k=4`),
};
