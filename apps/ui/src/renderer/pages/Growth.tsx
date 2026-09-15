import React from 'react';
import { Button, Form, Input, Modal, Select, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { intRule, threadsUrlListRule } from '../api/validators';
import { StatusTag } from '../components/ui';

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
      <Button type="primary" onClick={() => setOpen(true)}>Activity baru</Button>
      <Table size="small" rowKey="id" dataSource={rows}
        columns={[{ title: 'ID', dataIndex: 'id' }, { title: 'Kind', dataIndex: 'kind' },
          { title: 'Status', dataIndex: 'status', render: (s: string) => <StatusTag status={s} /> },
          { title: 'Stats', render: (_: unknown, r: { id: number }) => stats[r.id] ? `${stats[r.id].success}/${stats[r.id].jobs} (${stats[r.id].rate})` : '-' },
          { title: 'Aksi', render: (_: unknown, r: { id: number }) => (
            <Space>
              <Button size="small" onClick={() => setRun({ id: r.id })}>Start</Button>
              <Button size="small" onClick={() => unwrap<{ jobs: number; success: number; rate: number }>(api.get(`/activities/${r.id}/stats`)).then((d) => setStats((s) => ({ ...s, [r.id]: d })))}>Stats</Button>
              <Button size="small" onClick={() => act(() => api.post(`/activities/${r.id}/pause`), 'dipause')}>Pause</Button>
              <Button size="small" onClick={() => act(() => api.post(`/activities/${r.id}/resume`), 'diresume')}>Resume</Button>
            </Space>) }]} />
      <Modal open={open} title="Activity growth" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/activities', { kind: 'growth', account_filter: {}, actions: (v.types || []).map((t: string) => ({ type: t, template: v.template || '' })) }), 'dibuat').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="types" label="Aksi" rules={[{ required: true }]}>
            <Select mode="multiple" options={['like', 'follow', 'unfollow', 'reply', 'repost', 'quote'].map((t) => ({ value: t }))} /></Form.Item>
          <Form.Item name="template" label="Template spintax reply/quote"><Input.TextArea rows={2} placeholder="{keren|mantap} banget!" /></Form.Item>
        </Form>
      </Modal>
      <Modal open={!!run} title={`Start activity #${run?.id}`} onCancel={() => setRun(null)} onOk={() => runForm.submit()}>
        <Form form={runForm} layout="vertical" onFinish={(v) => act(() => api.post(`/activities/${run?.id}/start`, { targets: (v.targets || '').split('\n').filter(Boolean), filter: { count: Number(v.count) || undefined } }), 'job diantre').then(() => { setRun(null); runForm.resetFields(); })}>
          <Form.Item name="targets" label="Target (1 URL Threads/baris)" rules={[{ required: true }, threadsUrlListRule()]}><Input.TextArea rows={4} placeholder="https://www.threads.com/@akun/post/…" /></Form.Item>
          <Form.Item name="count" label="Sampling akun (kosong = semua)" rules={[intRule('Sampling', 1, 2000)]}><Input type="number" min={1} placeholder="cth 50" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
