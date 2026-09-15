import React from 'react';
import { Button, Form, Input, Modal, Select, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { intRule, threadsUrlListRule } from '../api/validators';
import { PageHeader, Panel, StatusTag, W } from '../components/ui';

export default function Growth() {
  const [rows, setRows] = React.useState<{ id: number; kind: string; status: string }[]>([]);
  const [open, setOpen] = React.useState(false);
  const [run, setRun] = React.useState<{ id: number } | null>(null);
  const [form] = Form.useForm();
  const [runForm] = Form.useForm();
  const [stats, setStats] = React.useState<Record<number, { jobs: number; success: number; rate: number }>>({});
  const load = React.useCallback(() => {
    unwrap<{ items: { id: number; kind: string; status: string }[] }>(api.get('/activities')).then((d) => setRows(d.items)).catch((e) => notifyError(e));
  }, []);
  React.useEffect(load, [load]);
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); message.success(ok); load(); } catch (e) { notifyError(e); }
  };
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <PageHeader title="Growth Automation" sub="like · follow · reply · repost · quote with human-like delays" />
      <Button type="primary" onClick={() => setOpen(true)}>New activity</Button>
      <Panel title="Activities" count={rows.length}>
      <Table size="small" rowKey="id" dataSource={rows} scroll={{ x: 900 }} pagination={{ pageSize: 12, showSizeChanger: false }}
        columns={[{ title: 'ID', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Kind', dataIndex: 'kind', width: W.kind },
          { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
          { title: 'Stats', dataIndex: 'id', width: 170, render: (_: unknown, r: { id: number }) => stats[r.id] ? `${stats[r.id].success}/${stats[r.id].jobs} (${stats[r.id].rate})` : '–' },
          { title: 'Actions', width: W.actionsMd, align: 'right' as const, render: (_: unknown, r: { id: number }) => (
            <Space size={6}>
              <Button size="small" onClick={() => setRun({ id: r.id })}>Start</Button>
              <Button size="small" onClick={() => unwrap<{ jobs: number; success: number; rate: number }>(api.get(`/activities/${r.id}/stats`)).then((d) => setStats((s) => ({ ...s, [r.id]: d })))}>Stats</Button>
              <Button size="small" onClick={() => act(() => api.post(`/activities/${r.id}/pause`), 'Paused')}>Pause</Button>
              <Button size="small" onClick={() => act(() => api.post(`/activities/${r.id}/resume`), 'Resumed')}>Resume</Button>
            </Space>) }]} />
      </Panel>
      <Modal open={open} title="Growth activity" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/activities', { kind: 'growth', account_filter: {}, actions: (v.types || []).map((t: string) => ({ type: t, template: v.template || '' })) }), 'Created').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="types" label="Actions" rules={[{ required: true, message: 'Pick at least 1 action' }]}>
            <Select mode="multiple" options={['like', 'follow', 'unfollow', 'reply', 'repost', 'quote'].map((t) => ({ value: t }))} /></Form.Item>
          <Form.Item name="template" label="Spintax template (reply/quote)"><Input.TextArea rows={2} placeholder="{awesome|brilliant} post!" /></Form.Item>
        </Form>
      </Modal>
      <Modal open={!!run} title={`Start activity #${run?.id}`} onCancel={() => setRun(null)} onOk={() => runForm.submit()}>
        <Form form={runForm} layout="vertical" onFinish={(v) => act(() => api.post(`/activities/${run?.id}/start`, { targets: (v.targets || '').split('\n').filter(Boolean), filter: { count: Number(v.count) || undefined } }), 'Jobs queued').then(() => { setRun(null); runForm.resetFields(); })}>
          <Form.Item name="targets" label="Targets (1 Threads URL per line)" rules={[{ required: true, message: 'At least 1 target is required' }, threadsUrlListRule()]}><Input.TextArea rows={4} placeholder="https://www.threads.com/@account/post/…" /></Form.Item>
          <Form.Item name="count" label="Account sampling (empty = all)" rules={[intRule('Sampling', 1, 2000)]}><Input type="number" min={1} placeholder="e.g. 50" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
