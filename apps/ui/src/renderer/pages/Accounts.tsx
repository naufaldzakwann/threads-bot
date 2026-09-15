import React from 'react';
import { Button, Form, Input, Modal, Select, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { PageHeader, Panel, StatusTag, W } from '../components/ui';

type Acc = { id: number; username: string; status: string; health_score: number; account_tier: string; account_role: string };

export default function Accounts() {
  const [rows, setRows] = React.useState<Acc[]>([]);
  const [sel, setSel] = React.useState<number[]>([]);
  const [open, setOpen] = React.useState(false);
  const [form] = Form.useForm();

  const load = React.useCallback(() => {
    unwrap<{ items: Acc[] }>(api.get('/accounts?limit=500')).then((d) => setRows(d.items)).catch((e) => notifyError(e));
  }, []);
  React.useEffect(load, [load]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); message.success(ok); load(); } catch (e) { notifyError(e); }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <PageHeader title="Threads Accounts" sub="brand vs buzzer tiers · scout vs actor roles" />
      <Space wrap>
        <Button type="primary" onClick={() => setOpen(true)}>Add account</Button>
        <Button disabled={!sel.length} onClick={() => act(() => api.post('/accounts/bulk', { ids: sel, op: 'pause' }), 'Paused')}>Pause</Button>
        <Button disabled={!sel.length} onClick={() => act(() => api.post('/accounts/bulk', { ids: sel, op: 'resume' }), 'Resumed')}>Resume</Button>
        <Button disabled={!sel.length} danger onClick={() => act(() => api.post('/accounts/bulk', { ids: sel, op: 'disable', confirm: sel.length <= 20 }), 'Disabled')}>Disable</Button>
      </Space>
      <Panel title="Accounts" count={rows.length}>
      <Table size="small" rowKey="id" dataSource={rows} scroll={{ x: 1080 }} pagination={{ pageSize: 15, showSizeChanger: false }}
        rowSelection={{ selectedRowKeys: sel, onChange: (k) => setSel(k as number[]) }}
        columns={[
          { title: 'Username', dataIndex: 'username', width: 200, ellipsis: true, className: 'mono' },
          { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
          { title: 'Health', dataIndex: 'health_score', width: W.health, align: 'center', className: 'num' },
          { title: 'Tier', dataIndex: 'account_tier', width: W.tier, ellipsis: true, className: 'mono' },
          { title: 'Role', dataIndex: 'account_role', width: W.role },
          { title: 'Actions', width: 330, align: 'right' as const, render: (_: unknown, r: Acc) => (
            <Space size={6}>
              <Button size="small" onClick={() => act(() => api.post(`/accounts/${r.id}/login`), 'Login queued')}>Login</Button>
              <Button size="small" onClick={() => act(() => api.post(`/accounts/${r.id}/resolve-checkpoint`), 'Resolve queued')}>Resolve</Button>
              <Select size="small" value={r.status} style={{ width: 132 }} onChange={(v) => act(() => api.post(`/accounts/${r.id}/status`, { status: v }), v)}
                options={['new', 'active', 'warming_up', 'checkpoint', 'restricted', 'disabled'].map((s) => ({ value: s, label: s }))} />
            </Space>) },
        ]} />
      </Panel>
      <Modal open={open} title="Add account" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/accounts', v), 'Account created').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="username" label="Username / handle" rules={[{ required: true, message: 'Username is required' }]}><Input /></Form.Item>
          <Form.Item name="password" label="Linked IG password"><Input.Password autoComplete="new-password" /></Form.Item>
          <Form.Item name="account_tier" label="Tier" initialValue="buzzer_satellite">
            <Select options={[{ value: 'brand_official' }, { value: 'buzzer_satellite' }]} /></Form.Item>
          <Form.Item name="account_role" label="Role" initialValue="actor">
            <Select options={[{ value: 'actor' }, { value: 'scout' }]} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
