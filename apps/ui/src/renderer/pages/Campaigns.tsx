import React from 'react';
import { Button, Col, Form, Input, Modal, Row, Select, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { idListRule, intRule, parseIdList, threadsUrlListRule } from '../api/validators';
import { PageHeader, Panel, StatusTag, W } from '../components/ui';

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
      <PageHeader title="Buzzer Campaigns" sub="1-click amplification · drip distribution · target-side pacing" />
      <Button type="primary" onClick={() => setOpen(true)}>New campaign</Button>
      <Panel title="Campaigns" count={rows.length}>
      <Table size="small" rowKey="id" dataSource={rows} scroll={{ x: 980 }} pagination={{ pageSize: 12, showSizeChanger: false }}
        columns={[{ title: 'ID', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Name', dataIndex: 'name', width: 220, ellipsis: true },
          { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
          { title: 'Progress', dataIndex: 'id', width: 150, render: (_: unknown, r: { id: number }) => prog[r.id] ? `${prog[r.id].done}/${prog[r.id].total} (${prog[r.id].rate})` : '–' },
          { title: 'Actions', width: W.actionsLg, align: 'right' as const, render: (_: unknown, r: { id: number }) => (
            <Space size={6} wrap>
              <Button size="small" onClick={() => showProg(r.id)}>Progress</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/start`), 'Running')}>Start</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/pause`), 'Paused')}>Pause</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/stop`), 'Stopped')}>Stop</Button>
              <Button size="small" onClick={() => act(() => api.post(`/campaigns/${r.id}/retry-failed`), 'Failures re-queued')}>Retry failed</Button>
            </Space>) }]} />
      </Panel>
      {parts.length > 0 && (
        <Panel title="Participants" count={parts.length}>
          <Table size="small" rowKey="id" dataSource={parts} pagination={{ pageSize: 10, showSizeChanger: false }}
            columns={[{ title: 'Account', dataIndex: 'account_id', width: W.account, className: 'num' }, { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> }]} />
        </Panel>)}
      <Modal open={open} title="Campaign wizard (condensed to 4 steps)" onCancel={() => setOpen(false)} onOk={() => form.submit()} width={640}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/campaigns', {
          name: v.name, targets: (v.targets || '').split('\n').filter(Boolean),
          actions: (v.actions || []).map((t: string) => ({ type: t })),
          account_ids: parseIdList(v.accounts || ''),
          spread_minutes: Number(v.spread) || 180, max_target_actions_per_minute: Number(v.pacing) || 4,
        }), 'Campaign created').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="name" label="1. Name" rules={[{ required: true, message: 'Name is required' }]}><Input /></Form.Item>
          <Form.Item name="targets" label="1. Targets (1–20 Threads post URLs per line)" rules={[{ required: true, message: 'At least 1 target is required' }, threadsUrlListRule(20)]}><Input.TextArea rows={2} placeholder="https://www.threads.com/@account/post/…" /></Form.Item>
          <Form.Item name="actions" label="2. Actions + preset"><Select mode="multiple" options={['like', 'reply', 'repost', 'quote'].map((t) => ({ value: t }))} /></Form.Item>
          <Form.Item name="accounts" label="3. Fleet (account IDs, comma — e.g. 1,2,3)" rules={[idListRule('Fleet')]}><Input placeholder="1,2,3" /></Form.Item>
          <Row gutter={[12, 0]}>
            <Col span={12}>
              <Form.Item name="spread" label="4. Spread in minutes (1–43200)" initialValue={180} rules={[intRule('Spread', 1, 43200)]}><Input type="number" min={1} /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="pacing" label="Target pacing per min (1–6)" initialValue={4} rules={[intRule('Pacing', 1, 6)]}><Input type="number" min={1} max={6} /></Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </Space>
  );
}
