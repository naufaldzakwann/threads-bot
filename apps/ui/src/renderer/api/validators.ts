/* Form validators — mirror of thbuzzer/utils/validators.py. Messages in English. */

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

const notThreadsMsg = 'Invalid URL — must be a Threads post link (e.g. https://www.threads.com/@account/post/…)';

/** A single Threads URL. */
export function threadsUrlRule() {
  return {
    validator: (_: unknown, v: string) => {
      if (!v || isThreadsUrl(v)) return Promise.resolve();
      return Promise.reject(new Error(notThreadsMsg));
    },
  };
}

/** Textarea: every non-empty line must be a Threads URL (+ optional max lines). */
export function threadsUrlListRule(maxLines?: number) {
  return {
    validator: (_: unknown, v: string) => {
      const lines = (v || '').split('\n').map((s) => s.trim()).filter(Boolean);
      if (!lines.length) return Promise.reject(new Error('Invalid: at least 1 Threads URL is required'));
      if (maxLines && lines.length > maxLines) {
        return Promise.reject(new Error(`Maximum ${maxLines} URLs (got ${lines.length})`));
      }
      const bad = lines.find((l) => !isThreadsUrl(l));
      if (bad) return Promise.reject(new Error(`${notThreadsMsg}: "${bad.slice(0, 60)}"`));
      return Promise.resolve();
    },
  };
}

/** Sensible integer. Value may be string (Input type=number) / number / empty. */
export function intRule(label: string, min = 1, max?: number) {
  return {
    validator: (_: unknown, v: unknown) => {
      if (v === undefined || v === null || v === '') return Promise.resolve(); // empty → handle with required separately
      const s = String(v).trim();
      if (!/^-?\d+$/.test(s)) return Promise.reject(new Error(`${label} is invalid: "${s}" is not a number`));
      const n = parseInt(s, 10);
      if (n < min) return Promise.reject(new Error(`${label} is invalid: minimum is ${min}`));
      if (max !== undefined && n > max) return Promise.reject(new Error(`${label} is invalid: maximum is ${max}`));
      return Promise.resolve();
    },
  };
}

export const accountIdRule = () => intRule('Account ID', 1);

/** "1,2,3" — every item must be a positive integer. */
export function idListRule(label = 'ID list') {
  return {
    validator: (_: unknown, v: string) => {
      const items = (v || '').split(',').map((s) => s.trim()).filter(Boolean);
      if (!items.length) return Promise.reject(new Error(`${label} is invalid: at least 1 ID is required`));
      const bad = items.find((s) => !/^\d+$/.test(s) || parseInt(s, 10) < 1);
      if (bad) return Promise.reject(new Error(`${label} is invalid: "${bad}" is not an account ID (integer ≥ 1)`));
      return Promise.resolve();
    },
  };
}

/** host:port[:user:pass] with port 1–65535. */
export function proxyRule() {
  return {
    validator: (_: unknown, v: string) => {
      const s = (v || '').trim();
      const m = s.replace(/^[a-z]+:\/\//i, '').split(':');
      if (m.length < 2) return Promise.reject(new Error('Invalid proxy: format host:port or host:port:user:pass'));
      const port = Number(m[1]);
      if (!m[0] || !Number.isInteger(port) || port < 1 || port > 65535) {
        return Promise.reject(new Error('Invalid proxy: port must be a number 1–65535'));
      }
      return Promise.resolve();
    },
  };
}

/** Generic http(s) URL (webhook, redirect URI). */
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
      } catch { /* fall through to reject */ }
      return Promise.reject(new Error(`${label} is invalid: must be an http(s) URL — e.g. https://…`));
    },
  };
}

/** Parse "1,2,3" → number[] (assumes idListRule passed). */
export function parseIdList(v: string): number[] {
  return (v || '').split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => Number.isInteger(n) && n >= 1);
}
