import React from 'react';
import { Card, Tag } from 'antd';

/** Kartu statistik dengan garis gradient — angka monospace ala terminal. */
export function StatCard({ label, value, hint, accent = '#22d3ee' }: {
  label: string; value: React.ReactNode; hint?: string; accent?: string;
}) {
  return (
    <Card size="small" className="glass stat-card" style={{ minWidth: 150, flex: '1 1 150px' }}>
      <div className="stat-label">{label}</div>
      <div className="stat-num" style={{ color: accent }}>{value}</div>
      {hint && <div style={{ color: '#94a3b8', fontSize: 11 }}>{hint}</div>}
    </Card>
  );
}

/** Tag status semantik konsisten (§MASTER): hijau run, amber antre, merah gagal, slate jeda, cyan live. */
export function StatusTag({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  const green = ['active', 'running', 'published', 'completed', 'done', 'alive', 'ok', 'success', 'visible'];
  const amber = ['scheduled', 'pending', 'queued', 'new', 'login_pending', 'warming_up'];
  const red = ['failed', 'restricted', 'checkpoint', 'dead_letter', 'suspended', 'hidden_by_platform', 'disabled', 'wrong_password'];
  const color = green.includes(s) ? 'green' : amber.includes(s) ? 'orange' : red.includes(s) ? 'red'
    : s.includes('pause') || s.includes('held') ? 'default' : 'cyan';
  return <Tag color={color} className="mono" style={{ fontSize: 11 }}>{status}</Tag>;
}

export function PageHeader({ title, sub, extra }: { title: string; sub?: string; extra?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{title}</h2>
      {sub && <span style={{ color: '#94a3b8', fontSize: 12 }}>{sub}</span>}
      <span style={{ flex: 1 }} />
      {extra}
    </div>
  );
}

export function EmptyHint({ text }: { text: string }) {
  return <div style={{ color: '#64748b', fontSize: 12, padding: '8px 0' }}>{text}</div>;
}
