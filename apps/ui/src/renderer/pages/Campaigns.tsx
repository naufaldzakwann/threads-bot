import React from 'react';
import { Button, Card, Form, Input, Modal, Select, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { idListRule, intRule, parseIdList, threadsUrlListRule } from '../api/validators';
import { StatusTag } from '../components/ui';

export default function Campaigns() {
  const [rows, setRows] = React.useState<{ id: number; name: string; status: string }[]>([]);
  const [open, setOpen] = React.useState(false);
  const [prog, setProg] = React.useState<Record<number, { total: number; done: number; rate: number }>>({});
  const [parts, setParts] = React.useState<{ id: number; account_id: number; status: string }[]>([]);
  const [form] = Form.useForm();
  const load = React.useCallback(() => {
    unwrap<{ items: { id: number; name: string; status: string }[] }>(api.get('/campaigns')).then((d) => setRows(d.items)).catch((e) => notifyError(e));
  }, []);
  React.useEffect(load, [load]);
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); message.success(ok); load(); } catch (e) { notifyError(e); }
  };
  const showProg = async (id: number) => {
    const p = await unwrap<{ total: number; done: number; rate: number }>(api.get(`/campaigns/${id}/progress`));
    const ps = await unwrap<{ items: { id: number; account_id: number; status: string }[] }>(api.get(`/campaigns/${id}/participants`));
    setProg((s) => ({ ...s, [id]: p }));
    setParts(ps.items);
  };
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Button type="primary" onClick={() => setOpen(true)}>Kampanye baru</Button>
      <Table size="small" rowKey="id" dataSource={rows}
        columns={[{ title: 'ID', dataIndex: 'id' }, { title: 'Nama', dataIndex: 'name' },
          { title: 'Status', dataIndex: 'status', render: (s: string) => <StatusTag status={s} /> },
          { title: 'Progres', render: (_: unknown, r: { id: number }) => prog[r.id] ? `${prog[r.id].done}/${prog[r.id].total} (${prog[r.id].rate})` : '-' },
          { title: 'Aksi', render: (_: unknown, r: { id: number }) => (
            <Space wrap>
              <Button size="small" onClick={() => showProg(r.id)}>Progress</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/start`), 'running')}>Start</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/pause`), 'dipause')}>Pause</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/stop`), 'distop')}>Stop</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/retry-failed`), 'gagal diantre ulang')}>Retry gagal</Button>
            </Space>) }]} />
      {parts.length > 0 && (
        <Card size="small" className="glass" title="Peserta (klik Progress)">
          <Table size="small" rowKey="id" dataSource={parts} pagination={{ pageSize: 10 }}
            columns={[{ title: 'Akun', dataIndex: 'account_id' }, { title: 'Status', dataIndex: 'status', render: (s: string) => <StatusTag status={s} /> }]} />
        </Card>)}
      <Modal open={open} title="Wizard kampanye (4 langkah diringkas)" onCancel={() => setOpen(false)} onOk={() => form.submit()} width={640}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/campaigns', {
          name: v.name, targets: (v.targets || '').split('\n').filter(Boolean),
          actions: (v.actions || []).map((t: string) => ({ type: t })),
          account_ids: parseIdList(v.accounts || ''),
          spread_minutes: Number(v.spread) || 180, max_target_actions_per_minute: Number(v.pacing) || 4,
        }), 'kampanye dibuat').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="name" label="1. Nama" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="targets" label="1. Target (1–20 URL postingan Threads/baris)" rules={[{ required: true }, threadsUrlListRule(20)]}><Input.TextArea rows={2} placeholder="https://www.threads.com/@akun/post/…" /></Form.Item>
          <Form.Item name="actions" label="2. Aksi + preset"><Select mode="multiple" options={['like', 'reply', 'repost', 'quote'].map((t) => ({ value: t }))} /></Form.Item>
          <Form.Item name="accounts" label="3. Armada (ID akun, koma — cth 1,2,3)" rules={[idListRule('Armada')]}><Input placeholder="1,2,3" /></Form.Item>
          <Space>
            <Form.Item name="spread" label="4. Spread (mnt, 1–43200)" initialValue={180} rules={[intRule('Spread', 1, 43200)]}><Input type="number" min={1} /></Form.Item>
            <Form.Item name="pacing" label="Target pacing/mnt (1–6)" initialValue={4} rules={[intRule('Pacing', 1, 6)]}><Input type="number" min={1} max={6} /></Form.Item>
          </Space>
        </Form>
      </Modal>
    </Space>
  );
}
