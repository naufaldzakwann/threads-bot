import React from 'react';
import { Badge, Card, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';

/** Stat card with gradient top border — monospace terminal-style numbers. */
export function StatCard({ label, value, hint, accent = '#22d3ee', style }: {
  label: string; value: React.ReactNode; hint?: string; accent?: string; style?: React.CSSProperties;
}) {
  return (
    <Card size="small" className="glass stat-card" style={{ width: '100%', ...style }}>
      <div className="stat-label">{label}</div>
      <div className="stat-num" style={{ color: accent }}>{value}</div>
      {hint && <div style={{ color: '#94a3b8', fontSize: 11 }}>{hint}</div>}
    </Card>
  );
}

/** Consistent semantic status tag (see MASTER): green = running, amber = queued,
 * red = failed, slate = paused, cyan = live/misc. */
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

/** Standard panel: every data table on every page shares this frame. */
export function Panel({ title, count, extra, children, style }: {
  title: string; count?: number; extra?: React.ReactNode; children: React.ReactNode; style?: React.CSSProperties;
}) {
  return (
    <Card size="small" className="glass pro-table" style={style}
      title={<span style={{ fontSize: 13, fontWeight: 600 }}>{title}{' '}
        {count !== undefined && <Badge count={count} color="#155e75" style={{ marginLeft: 4 }} />}</span>}
      extra={extra}>
      {children}
    </Card>
  );
}

/** Column-width rhythm shared by all tables (px). */
export const W = {
  id: 76, status: 138, health: 96, account: 96, tier: 152, role: 104,
  kind: 120, type: 150, time: 184, latency: 110, country: 104, port: 88,
  tag: 130, days: 100, actionsSm: 220, actionsMd: 320, actionsLg: 430,
};

/** Narrow monospace ID column. */
export const colID = (title = 'ID'): ColumnsType<never>[number] => ({
  title, dataIndex: 'id', width: W.id, className: 'mono', sorter: false,
} as never);

/** Status column with the semantic tag. */
export const colStatus = (title = 'Status'): ColumnsType<never>[number] => ({
  title, dataIndex: 'status', width: W.status, render: ((s: string) => <StatusTag status={s} />) as never,
} as never);
