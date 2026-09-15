/* Client REST + WS ke thbuzzer-core. Auto-connect via /connection.json (ditulis backend
   tiap start), fallback ke localStorage, terakhir input manual. Tahan restart backend:
   bila fetch gagal (port/token basi), refresh connection.json dan coba sekali lagi. */

import { message } from 'antd';

let _base = '';
let _token = '';
let _lastToast = 0;

export function coreBase(): string {
  return _base || localStorage.getItem('thb.base') || 'http://127.0.0.1:8899';
}

export function coreToken(): string {
  return _token || localStorage.getItem('thb.token') || '';
}

export function setConnection(base: string, token: string, persist = true) {
  _base = base;
  _token = token;
  if (persist) {
    localStorage.setItem('thb.base', base);
    localStorage.setItem('thb.token', token);
  }
}

/** Dipanggil sekali saat boot: coba connection.json, lalu simpan bila valid. */
export async function autoConnect(): Promise<{ base: string; token: string; auto: boolean }> {
  try {
    const r = await fetch(`connection.json?t=${Date.now()}`, { cache: 'no-store' });
    if (r.ok) {
      const j = await r.json();
      if (j.base && j.token) {
        const ping = await fetch(j.base + '/healthz', { cache: 'no-store' });
        if (ping.ok) {
          setConnection(j.base, j.token);
          return { base: j.base, token: j.token, auto: true };
        }
      }
    }
  } catch { /* fallback manual */ }
  return { base: coreBase(), token: coreToken(), auto: false };
}

/** Notifikasi error ramah + throttle (1 per 4 dtk, key sama → tidak menumpuk). */
export function notifyError(e: unknown) {
  const now = Date.now();
  if (now - _lastToast < 4000) return;
  _lastToast = now;
  const raw = String((e as Error)?.message ?? e);
  const friendly = raw.includes('Failed to fetch')
    ? `Core tidak terjangkau di ${coreBase()} — backend mungkin restart. Mencoba sambung ulang otomatis…`
    : raw;
  message.error({ content: friendly.length > 240 ? friendly.slice(0, 240) + '…' : friendly, key: 'thb-err', duration: 4 });
}

async function doFetch(method: string, path: string, body?: unknown) {
  const r = await fetch(coreBase() + path, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${coreToken()}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) throw new Error(typeof data === 'string' ? data : JSON.stringify(data));
  return data as never;
}

async function req(method: string, path: string, body?: unknown) {
  try {
    return await doFetch(method, path, body);
  } catch (e) {
    if (e instanceof TypeError) {
      // Kemungkinan backend restart (port/token baru) → refresh koneksi, coba sekali lagi
      try {
        const { auto } = await autoConnect();
        if (auto) return await doFetch(method, path, body);
      } catch { /* lanjut ke error ramah */ }
    }
    throw e;
  }
}

export const api = {
  get: (p: string) => req('GET', p) as Promise<never>,
  post: (p: string, b?: unknown) => req('POST', p, b ?? {}) as Promise<never>,
  del: (p: string) => req('DELETE', p) as Promise<never>,
};

export function connectWS(onEvent: (e: { event: string } & Record<string, unknown>) => void): WebSocket {
  const ws = new WebSocket(coreBase().replace('http', 'ws') + '/ws');
  ws.onmessage = (m) => {
    try { onEvent(JSON.parse(m.data)); } catch { /* abaikan */ }
  };
  return ws;
}

export async function unwrap<T>(p: Promise<never>): Promise<T> {
  return (await p) as unknown as T;
}
