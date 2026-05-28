const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) {
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || res.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data as T;
}

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: form,
  });
  if (res.status === 401) {
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || res.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data as T;
}

// Загрузка файла с прогрессом. fetch не отдаёт upload-прогресс, поэтому XHR.
// onProgress(percent): 0..100 по факту отправки байт. После 100% сервер ещё
// обрабатывает (напр. ffmpeg-квадрат для кружка) — это уже не upload, вызывающий
// код показывает «Обработка…» пока промис не зарезолвится.
function requestFormProgress<T>(
  path: string,
  form: FormData,
  onProgress?: (percent: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}${path}`);
    xhr.withCredentials = true;
    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }
    xhr.onload = () => {
      if (xhr.status === 401) {
        if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
          window.location.href = '/login';
        }
        reject(new Error('Unauthorized'));
        return;
      }
      const text = xhr.responseText;
      let data: unknown = null;
      try { data = text ? JSON.parse(text) : null; } catch { /* не-JSON ответ */ }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve((xhr.status === 204 ? undefined : data) as T);
      } else {
        const d = data as { detail?: unknown; message?: unknown } | null;
        const detail = (d && (d.detail || d.message)) || xhr.statusText || `HTTP ${xhr.status}`;
        reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)));
      }
    };
    xhr.onerror = () => reject(new Error('Не удалось загрузить файл (сеть недоступна)'));
    xhr.send(form);
  });
}

export const api = {
  get: <T,>(p: string) => request<T>('GET', p),
  post: <T,>(p: string, b?: unknown) => request<T>('POST', p, b),
  postForm: <T,>(p: string, form: FormData) => requestForm<T>(p, form),
  postFormProgress: <T,>(p: string, form: FormData, onProgress?: (percent: number) => void) =>
    requestFormProgress<T>(p, form, onProgress),
  patch: <T,>(p: string, b?: unknown) => request<T>('PATCH', p, b),
  del: <T,>(p: string) => request<T>('DELETE', p),
};

export const fetcher = <T,>(p: string) => api.get<T>(p);
