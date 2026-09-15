import React from 'react';
import { Button, Form, Input, Modal, Select, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { PageHeader, StatusTag } from '../components/ui';

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
      <PageHeader title="Akun Threads" sub="tier brand vs buzzer · role scout vs actor" />
      <Space wrap>
        <Button type="primary" onClick={() => setOpen(true)}>Tambah akun</Button>
        <Button disabled={!sel.length} onClick={() => act(() => api.post('/accounts/bulk', { ids: sel, op: 'pause' }), 'dipause')}>Pause</Button>
        <Button disabled={!sel.length} onClick={() => act(() => api.post('/accounts/bulk', { ids: sel, op: 'resume' }), 'diresume')}>Resume</Button>
        <Button disabled={!sel.length} danger onClick={() => act(() => api.post('/accounts/bulk', { ids: sel, op: 'disable', confirm: sel.length <= 20 }), 'dinonaktifkan')}>Disable</Button>
      </Space>
      <Table size="small" rowKey="id" dataSource={rows} rowSelection={{ selectedRowKeys: sel, onChange: (k) => setSel(k as number[]) }}
        columns={[
          { title: 'Username', dataIndex: 'username' },
          { title: 'Status', dataIndex: 'status', render: (s: string) => <StatusTag status={s} /> },
          { title: 'Health', dataIndex: 'health_score' },
          { title: 'Tier', dataIndex: 'account_tier' },
          { title: 'Role', dataIndex: 'account_role' },
          { title: 'Aksi', render: (_: unknown, r: Acc) => (
            <Space>
              <Button size="small" onClick={() => act(() => api.post(`/accounts/${r.id}/login`), 'login diantre')}>Login</Button>
              <Button size="small" onClick={() => act(() => api.post(`/accounts/${r.id}/resolve-checkpoint`), 'resolve diantre')}>Resolve</Button>
              <Select size="small" value={r.status} style={{ width: 150 }} onChange={(v) => act(() => api.post(`/accounts/${r.id}/status`, { status: v }), v)}
                options={['new', 'active', 'warming_up', 'checkpoint', 'restricted', 'disabled'].map((s) => ({ value: s, label: s }))} />
            </Space>) },
        ]} />
      <Modal open={open} title="Tambah akun" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/accounts', v), 'akun dibuat').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="username" label="Username/Handle" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="password" label="Password IG"><Input.Password /></Form.Item>
          <Form.Item name="account_tier" label="Tier" initialValue="buzzer_satellite">
            <Select options={[{ value: 'brand_official' }, { value: 'buzzer_satellite' }]} /></Form.Item>
          <Form.Item name="account_role" label="Role" initialValue="actor">
            <Select options={[{ value: 'actor' }, { value: 'scout' }]} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
