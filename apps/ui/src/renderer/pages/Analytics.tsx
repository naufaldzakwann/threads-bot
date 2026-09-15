import React from 'react';
import { Button, Card, Input, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { PageHeader, Panel, StatusTag, W } from '../components/ui';
import * as echarts from 'echarts';

export default function Analytics() {
  const [logs, setLogs] = React.useState<{ id: number; action: string; status: string; message: string }[]>([]);
  const [jobs, setJobs] = React.useState<{ id: number; type: string; status: string }[]>([]);
  const [dead, setDead] = React.useState<{ id: number; type: string }[]>([]);
  const [rec, setRec] = React.useState<{ name: string; note: string; enabled: number }[]>([]);
  const [aid, setAid] = React.useState('1');
  const chartRef = React.useRef<HTMLDivElement>(null);

  const load = React.useCallback(() => {
    unwrap<{ items: never[] }>(api.get('/analytics/logs?limit=100')).then((d) => setLogs(d.items as never)).catch(() => undefined);
    unwrap<{ items: never[] }>(api.get('/analytics/jobs?limit=200')).then((d) => setJobs(d.items as never)).catch(() => undefined);
    unwrap<{ items: never[] }>(api.get('/analytics/dead-letter')).then((d) => setDead(d.items as never)).catch(() => undefined);
    unwrap<{ items: never[] }>(api.get('/analytics/recurring')).then((d) => setRec(d.items as never)).catch(() => undefined);
  }, []);
  React.useEffect(load, [load]);

  const validAid = /^\d+$/.test(aid.trim()) && parseInt(aid, 10) >= 1;

  const loadSeries = async () => {
    if (!validAid) {
      message.error('Account ID is invalid: must be a number ≥ 1');
      return;
    }
    try {
      const d = await unwrap<{ items: { t: number; followers: number }[] }>(api.get(`/analytics/series/account?account_id=${aid}&days=30`));
      const el = chartRef.current;
      if (el) {
        const ch = echarts.init(el);
        ch.setOption({ xAxis: { type: 'category', data: d.items.map((x) => new Date(x.t * 1000).toLocaleDateString('en-US')) },
          yAxis: { type: 'value' }, series: [{ type: 'line', data: d.items.map((x) => x.followers) }] });
      }
      if (!d.items.length) message.info('No snapshots yet — click Snapshot now.');
    } catch (e) { notifyError(e); }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <PageHeader title="Analytics" sub="follower curves · job inspector · audit log" />
      <Card size="small" className="glass" title="Follower curve per account">
        <Space>
          <Input value={aid} onChange={(e) => setAid(e.target.value)} type="number" min={1} style={{ width: 120 }} aria-label="Account ID" status={aid && !validAid ? 'error' : undefined} />
          <Button onClick={loadSeries}>Load</Button>
          <Button onClick={async () => {
            if (!validAid) { message.error('Account ID is invalid: must be a number ≥ 1'); return; }
            await api.post('/analytics/snapshot-now', { account_id: Number(aid) }); message.success('Snapshot queued');
          }}>Snapshot now</Button>
        </Space>
        <div ref={chartRef} style={{ height: 220, marginTop: 8 }} />
      </Card>
      <Panel title="Jobs" count={jobs.length}>
        <Table size="small" rowKey="id" dataSource={jobs} pagination={{ pageSize: 8, showSizeChanger: false }}
          columns={[{ title: 'ID', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Type', dataIndex: 'type', width: W.type, ellipsis: true, className: 'mono' },
            { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
            { title: 'Actions', width: W.actionsSm, align: 'right' as const, render: (_: unknown, r: { id: number }) => (
              <Space size={6}><Button size="small" onClick={async () => { await api.post(`/analytics/jobs/${r.id}/retry`); load(); }}>Retry</Button>
                <Button size="small" danger onClick={async () => { await api.post(`/analytics/jobs/${r.id}/cancel`); load(); }}>Cancel</Button></Space>) }]} />
      </Panel>
      <Card size="small" className="glass" title={`Dead letter (${dead.length})`}>
        {dead.map((d) => <Tag key={d.id} color="red">{d.id}:{d.type}</Tag>)}
      </Card>
      <Card size="small" className="glass" title="Recurring">
        {rec.map((r) => <div key={r.name}><Tag color={r.enabled ? 'green' : 'default'}>{r.enabled ? 'on' : 'off'}</Tag> {r.name} — {r.note}
          <Button size="small" type="link" onClick={async () => { await api.post(`/analytics/recurring/${r.name}`, { enabled: !r.enabled }); load(); }}>toggle</Button></div>)}
      </Card>
      <Panel title="Activity log" count={logs.length}>
        <Table size="small" rowKey="id" dataSource={logs} pagination={{ pageSize: 8, showSizeChanger: false }}
          columns={[{ title: 'ID', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Action', dataIndex: 'action', width: W.type, ellipsis: true, className: 'mono' }, { title: 'Status', dataIndex: 'status', width: W.status }, { title: 'Message', dataIndex: 'message', ellipsis: true }]} />
      </Panel>
    </Space>
  );
}
