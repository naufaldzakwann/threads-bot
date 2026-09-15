import React from 'react';
import { Button, Form, Input, Modal, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { proxyRule } from '../api/validators';
import { PageHeader, Panel, StatusTag, W } from '../components/ui';

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
      <PageHeader title="Proxies" sub="sticky per account · max 3 accounts/proxy · health-checked every 30 min" />
      <Space>
        <Button type="primary" onClick={() => setOpen(true)}>Add proxy</Button>
        <Button onClick={() => act(() => api.post('/proxies/test-all'), 'Health check finished')}>Test all</Button>
      </Space>
      <Panel title="Proxies" count={rows.length}>
      <Table size="small" rowKey="id" dataSource={rows} pagination={{ pageSize: 15, showSizeChanger: false }}
        columns={[{ title: 'Host', dataIndex: 'host', width: 220, ellipsis: true, className: 'mono' },
          { title: 'Port', dataIndex: 'port', width: W.port, align: 'right' as const, className: 'num' },
          { title: 'Country', dataIndex: 'country', width: W.country, align: 'center' as const },
          { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
          { title: 'Latency', dataIndex: 'latency_ms', width: W.latency, align: 'right' as const, render: (v: number) => `${v} ms` }]} />
      </Panel>
      <Modal open={open} title="Add proxy" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/proxies', v), 'Proxy added').then(() => { setOpen(false); form.resetFields(); })}>
          <Form.Item name="url" label="host:port or host:port:user:pass" rules={[{ required: true, message: 'Proxy URL is required' }, proxyRule()]}><Input placeholder="127.0.0.1:8080" className="mono" /></Form.Item>
          <Form.Item name="country" label="Country"><Input placeholder="ID" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
