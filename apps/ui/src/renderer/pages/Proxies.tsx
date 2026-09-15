import React from 'react';
import { Button, Form, Input, Modal, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { proxyRule } from '../api/validators';

type Px = { id: number; host: string; port: number; status: string; latency_ms: number; country: string };

export default function Proxies() {
  const [rows, setRows] = React.useState<Px[]>([]);
  const [open, setOpen] = React.useState(false);
  const [form] = Form.useForm();
  const load = React.useCallback(() => {
    unwrap<{ items: Px[] }>(api.get('/proxies')).then((d) => setRows(d.items)).catch((e) => notifyError(e));
  }, []);
  React.useEffect(load, [load]);
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); message.success(ok); load(); } catch (e) { notifyError(e); }
  };
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Button type="primary" onClick={() => setOpen(true)}>Tambah proxy</Button>
        <Button onClick={() => act(() => api.post('/proxies/test-all'), 'health-check selesai')}>Test semua</Button>
      </Space>
      <Table size="small" rowKey="id" dataSource={rows}
        columns={[{ title: 'Host', dataIndex: 'host' }, { title: 'Port', dataIndex: 'port' },
          { title: 'Country', dataIndex: 'country' },
          { title: 'Status', dataIndex: 'status', render: (s: string) => <Tag color={s === 'alive' ? 'green' : s === 'dead' ? 'red' : 'orange'}>{s}</Tag> },
          { title: 'Latensi', dataIndex: 'latency_ms', render: (v: number) => `${v} ms` }]} />
      <Modal open={open} title="Tambah proxy" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/proxies', v), 'proxy ditambah').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="url" label="host:port atau host:port:user:pass" rules={[{ required: true }, proxyRule()]}><Input placeholder="127.0.0.1:8080" className="mono" /></Form.Item>
          <Form.Item name="country" label="Country"><Input placeholder="ID" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
