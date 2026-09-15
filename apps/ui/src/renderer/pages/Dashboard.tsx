import React from 'react';
import { Button, Card, Space, Table } from 'antd';
import { SyncOutlined } from '@ant-design/icons';
import { api, unwrap } from '../api/client';
import { EmptyHint, PageHeader, Panel, StatCard, StatusTag, W } from '../components/ui';

type Ev = { event: string } & Record<string, unknown>;

function evClass(ev: string): string {
  if (/fail|restrict|checkpoint|error/i.test(ev)) return 'ev-err';
  if (/quota|warn|alert|held|pause/i.test(ev)) return 'ev-warn';
  if (/ok|publish|done|completed|active/i.test(ev)) return 'ev-ok';
  return 'ev-info';
}

export default function Dashboard({ feed, connected }: { feed: Ev[]; connected: boolean }) {
  const [data, setData] = React.useState<{ accounts_by_status?: Record<string, number>; actions_24h?: number } | null>(null);
  const [jobs, setJobs] = React.useState<{ id: number; type: string; status: string }[]>([]);
  const [queue, setQueue] = React.useState(0);
  const [err, setErr] = React.useState('');

  const load = React.useCallback(() => {
    if (!connected) return;
    unwrap<{ accounts_by_status: Record<string, number>; actions_24h: number }>(api.get('/analytics/dashboard'))
      .then((d) => { setData(d); setErr(''); }).catch((e) => setErr(String(e)));
    unwrap<{ items: { id: number; type: string; status: string }[] }>(api.get('/analytics/jobs?status=running'))
      .then((d) => setJobs(d.items)).catch(() => undefined);
    unwrap<{ items: unknown[] }>(api.get('/analytics/jobs?status=pending'))
      .then((d) => setQueue(d.items.length)).catch(() => undefined);
  }, [connected]);

  React.useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const byStatus = data?.accounts_by_status || {};
  const total = Object.values(byStatus).reduce((a, b) => a + b, 0);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={14}>
      <PageHeader title="Command Deck" sub="fleet status + real-time scheduler"
        extra={<Button size="small" icon={<SyncOutlined />} onClick={load}>Refresh</Button>} />
      {err && <Card size="small" className="glass" style={{ borderColor: '#dc2626' }}>Core is not connected: {err}</Card>}
      {!connected && !err && <Card size="small" className="glass">Waiting for the core connection…</Card>}

      <div className="hero glass" style={{ padding: '18px 20px', display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flex: '0 0 250px' }}>
          <span className="live-dot" />
          <div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>Scheduler {connected ? 'online' : 'offline'}</div>
            <div className="mono" style={{ color: '#94a3b8', fontSize: 11 }}>1s tick · 3-layer limiter</div>
            <div className="mono" style={{ color: '#94a3b8', fontSize: 11 }}>kill-switch Ctrl+Shift+X</div>
          </div>
        </div>
        <div className="hero-stats">
          <StatCard label="accounts" value={total} hint={`${byStatus.active || 0} active`} accent="#22d3ee" />
          <StatCard label="actions 24h" value={data?.actions_24h ?? '–'} accent="#4ade80" />
          <StatCard label="running jobs" value={jobs.length} accent="#8b5cf6" />
          <StatCard label="queue" value={queue} hint="pending" accent="#f59e0b" />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Card size="small" className="glass" title="Fleet by status" style={{ flex: '1 1 320px' }}>
          {Object.keys(byStatus).length === 0 && <EmptyHint text="No accounts yet — add some on the Threads Accounts page." />}
          {Object.entries(byStatus).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid #1e293b' }}>
              <StatusTag status={k} />
              <span style={{ flex: 1 }} />
              <span className="mono" style={{ fontSize: 16 }}>{v}</span>
            </div>))}
        </Card>
        <Card size="small" className="glass" title={<span><span className="live-dot" style={{ marginRight: 8 }} />Live feed</span>} style={{ flex: '2 1 420px' }}>
          <div className="thb-feed">
            {feed.length === 0 && <span style={{ color: '#64748b' }}>$ thbuzzer --watch — waiting for events…</span>}
            {feed.slice(-14).reverse().map((e, i) => (
              <div key={i}><span className={evClass(e.event)}>▸ {e.event}</span>{' '}
                <span style={{ color: '#64748b' }}>{JSON.stringify(e).slice(0, 150)}</span></div>))}
          </div>
        </Card>
      </div>

      <Panel title="Running jobs" count={jobs.length}>
        <Table size="small" rowKey="id" dataSource={jobs} pagination={false}
          columns={[{ title: 'ID', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Type', dataIndex: 'type', width: 240, ellipsis: true, className: 'mono' },
            { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> }]} />
      </Panel>
    </Space>
  );
}
