/* Validator form — cerminan thbuzzer/utils/validators.py. Pesan Bahasa Indonesia. */

const THREADS_HOSTS = ['threads.com', 'www.threads.com', 'threads.net', 'www.threads.net'];

export function isThreadsUrl(raw: string): boolean {
  const v = (raw || '').trim();
  if (!v) return false;
  const s = v.includes('://') ? v : `https://${v}`;
  try {
    const u = new URL(s);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
    if (!THREADS_HOSTS.includes(u.hostname.toLowerCase())) return false;
    return /(\/post\/|\/t\/)/i.test(u.pathname);
  } catch {
    return false;
  }
}

const notThreadsMsg = 'URL tidak valid — harus link postingan Threads (contoh https://www.threads.com/@akun/post/…)';

/** Satu URL Threads. */
export function threadsUrlRule() {
  return {
    validator: (_: unknown, v: string) => {
      if (!v || isThreadsUrl(v)) return Promise.resolve();
      return Promise.reject(new Error(notThreadsMsg));
    },
  };
}

/** Textarea: tiap baris non-kosong wajib URL Threads (+ opsi maks baris). */
export function threadsUrlListRule(maxLines?: number) {
  return {
    validator: (_: unknown, v: string) => {
      const lines = (v || '').split('\n').map((s) => s.trim()).filter(Boolean);
      if (!lines.length) return Promise.reject(new Error('Wajib diisi minimal 1 URL Threads'));
      if (maxLines && lines.length > maxLines) {
        return Promise.reject(new Error(`Maksimal ${maxLines} URL (diisi ${lines.length})`));
      }
      const bad = lines.find((l) => !isThreadsUrl(l));
      if (bad) return Promise.reject(new Error(`${notThreadsMsg}: "${bad.slice(0, 60)}"`));
      return Promise.resolve();
    },
  };
}

/** Angka bulat masuk akal. value bisa string (Input type=number) / number / kosong. */
export function intRule(label: string, min = 1, max?: number) {
  return {
    validator: (_: unknown, v: unknown) => {
      if (v === undefined || v === null || v === '') return Promise.resolve(); // kosong → atur required terpisah
      const s = String(v).trim();
      if (!/^-?\d+$/.test(s)) return Promise.reject(new Error(`${label} tidak valid: "${s}" bukan angka`));
      const n = parseInt(s, 10);
      if (n < min) return Promise.reject(new Error(`${label} tidak valid: minimal ${min}`));
      if (max !== undefined && n > max) return Promise.reject(new Error(`${label} tidak valid: maksimal ${max}`));
      return Promise.resolve();
    },
  };
}

export const accountIdRule = () => intRule('Account ID', 1);

/** "1,2,3" — tiap item wajib angka ≥1. */
export function idListRule(label = 'Daftar ID') {
  return {
    validator: (_: unknown, v: string) => {
      const items = (v || '').split(',').map((s) => s.trim()).filter(Boolean);
      if (!items.length) return Promise.reject(new Error(`${label} tidak valid: minimal 1 ID`));
      const bad = items.find((s) => !/^\d+$/.test(s) || parseInt(s, 10) < 1);
      if (bad) return Promise.reject(new Error(`${label} tidak valid: "${bad}" bukan ID akun (angka ≥ 1)`));
      return Promise.resolve();
    },
  };
}

/** host:port[:user:pass] dengan port 1–65535. */
export function proxyRule() {
  return {
    validator: (_: unknown, v: string) => {
      const s = (v || '').trim();
      const m = s.replace(/^[a-z]+:\/\//i, '').split(':');
      if (m.length < 2) return Promise.reject(new Error('Proxy tidak valid: format host:port atau host:port:user:pass'));
      const port = Number(m[1]);
      if (!m[0] || !Number.isInteger(port) || port < 1 || port > 65535) {
        return Promise.reject(new Error('Proxy tidak valid: port harus angka 1–65535'));
      }
      return Promise.resolve();
    },
  };
}

/** URL http(s) umum (webhook, redirect URI). */
export function httpUrlRule(label = 'URL') {
  return {
    validator: (_: unknown, v: string) => {
      const s = (v || '').trim();
      if (!s) return Promise.resolve();
      try {
        const u = new URL(s.includes('://') ? s : `https://${s}`);
        if ((u.protocol === 'http:' || u.protocol === 'https:') && u.hostname.includes('.')) {
          return Promise.resolve();
        }
      } catch { /* jatuh ke reject */ }
      return Promise.reject(new Error(`${label} tidak valid: harus URL http(s) — contoh https://…`));
    },
  };
}

/** Parse "1,2,3" → number[] (asumsi lolos idListRule). */
export function parseIdList(v: string): number[] {
  return (v || '').split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => Number.isInteger(n) && n >= 1);
}
