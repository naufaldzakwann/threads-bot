import React from 'react';
import { Button, Card, Col, Form, Input, Row, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { accountIdRule, httpUrlRule } from '../api/validators';
import { PageHeader, Panel, W } from '../components/ui';

export default function Settings() {
  const [kv, setKv] = React.useState<Record<string, string>>({});
  const [tokens, setTokens] = React.useState<{ id: number; account_id: number; expires_at: number; days_left: number; needs_refresh: boolean }[]>([]);
  const [info, setInfo] = React.useState<Record<string, unknown> | null>(null);
  const [form] = Form.useForm();
  const [alertForm] = Form.useForm();
  const [oauth] = Form.useForm();

  const load = React.useCallback(() => {
    unwrap<Record<string, string>>(api.get('/settings')).then(setKv).catch((e) => notifyError(e));
    unwrap<{ items: never[] }>(api.get('/engines/threads-tokens')).then((d) => setTokens(d.items as never)).catch(() => undefined);
    unwrap<Record<string, unknown>>(api.get('/system/info')).then(setInfo).catch(() => undefined);
  }, []);
  React.useEffect(load, [load]);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <PageHeader title="Settings" sub="backend · OAuth · alerts · key-value store" />
      <Card size="small" className="glass" title="Backend info"><pre style={{ fontSize: 11 }}>{JSON.stringify(info, null, 1)}</pre>
        <Space>
          <Button danger size="small" onClick={async () => { await api.post('/system/killswitch', { scope: 'global', on: true }); message.warning('Global KILL engaged'); }}>Global KILL</Button>
          <Button size="small" onClick={async () => { await api.post('/system/killswitch', { scope: 'global', on: false }); message.success('Scheduler resumed'); }}>Resume</Button>
        </Space></Card>
      <Card size="small" className="glass" title="Threads OAuth (brand_official tier)">
        <div className="mono" style={{ color: '#94a3b8', fontSize: 11, marginBottom: 12 }}>Step 1 — build the authorize URL, open it, copy the code. Step 2 — exchange the code for a 60-day token.</div>
        <Form form={oauth} layout="vertical" className="form-grid" onFinish={async (v) => {
          try {
            const r = await unwrap<{ authorize_url: string }>(api.post('/engines/oauth/start', { app_id: v.app_id, redirect_uri: v.redirect, scopes: undefined }));
            message.info('Open this URL, copy the code, then exchange it below.');
            (document.getElementById('oauth-url') as HTMLAnchorElement | null)?.setAttribute('href', r.authorize_url);
          } catch (e) { notifyError(e); }
        }}>
          <Row gutter={[12, 0]}>
            <Col span={6}>
              <Form.Item name="app_id" label="Meta App ID" rules={[{ required: true, message: 'App ID is required' }]}><Input placeholder="e.g. 123456789" className="mono" /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="redirect" label="Redirect URI" rules={[{ required: true, message: 'Redirect URI is required' }, httpUrlRule('Redirect URI')]}><Input placeholder="https://…" style={{ width: '100%' }} className="mono" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label=" ">
                <Space>
                  <Button htmlType="submit">Build authorize URL</Button>
                  <a id="oauth-url" target="_blank" rel="noreferrer">authorize →</a>
                </Space>
              </Form.Item>
            </Col>
          </Row>
        </Form>
        <Form layout="vertical" className="form-grid" style={{ marginTop: 4 }} onFinish={async (v) => {
          try {
            const r = await unwrap<{ token_id: number }>(api.post('/engines/oauth/callback', { ...v, account_id: Number(v.account_id) }));
            message.success(`Token stored #${r.token_id}`); load();
          } catch (e) { notifyError(e); }
        }}>
          <Row gutter={[12, 0]}>
            <Col span={5}>
              <Form.Item name="account_id" label="Account ID" rules={[{ required: true, message: 'Account ID is required' }, accountIdRule()]}><Input type="number" min={1} placeholder="e.g. 3" autoComplete="off" /></Form.Item>
            </Col>
            <Col span={7}>
              <Form.Item name="code" label="Authorization code" rules={[{ required: true, message: 'Code is required' }]}><Input placeholder="paste code here" className="mono" autoComplete="off" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="app_id" label="Meta App ID" rules={[{ required: true, message: 'App ID is required' }]}><Input placeholder="e.g. 123456789" className="mono" autoComplete="off" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="app_secret" label="App secret" rules={[{ required: true, message: 'App secret is required' }]}><Input.Password placeholder="••••••••" autoComplete="new-password" /></Form.Item>
            </Col>
          </Row>
          <Row gutter={[12, 0]}>
            <Col span={12}>
              <Form.Item name="redirect_uri" label="Redirect URI (must match step 1)" rules={[{ required: true, message: 'Redirect URI is required' }, httpUrlRule('Redirect URI')]}><Input placeholder="https://…" style={{ width: '100%' }} className="mono" /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label=" ">
                <Button type="primary" htmlType="submit">Exchange code → token</Button>
              </Form.Item>
            </Col>
          </Row>
        </Form>
        <Panel title="OAuth tokens" count={tokens.length}>
        <Table size="small" rowKey="id" dataSource={tokens} pagination={false} style={{ marginTop: 8 }}
          columns={[{ title: 'Account', dataIndex: 'account_id', width: W.account, align: 'center' as const, className: 'num' },
            { title: 'Days left', dataIndex: 'days_left', width: W.days, align: 'center' as const, className: 'num' },
            { title: 'Actions', width: W.actionsSm, align: 'right' as const, render: (_: unknown, r: { id: number }) => (
              <Space size={6}><Button size="small" onClick={async () => { try { await api.post(`/engines/threads-tokens/${r.id}/test`); message.success('Token is valid'); } catch (e) { notifyError(e); } }}>Test</Button>
                <Button size="small" onClick={async () => { try { await api.post(`/engines/threads-tokens/${r.id}/refresh`, {}); message.success('Refreshed'); load(); } catch (e) { notifyError(e); } }}>Refresh</Button></Space>) }]} />
        </Panel>
      </Card>
      <Card size="small" className="glass" title="Alerts (desktop + webhook + Telegram)">
        <Form form={alertForm} layout="vertical" className="form-grid" onFinish={async (v) => {
          try { await api.post('/alerts/settings', v); message.success('Alerts saved'); }
          catch (e) { notifyError(e); }
        }}>
          <Row gutter={[12, 0]}>
            <Col span={10}>
              <Form.Item name="alerts.webhook_url" label="Generic JSON webhook URL" rules={[httpUrlRule('Webhook URL')]}><Input placeholder="https://…" className="mono" /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="alerts.telegram_bot_token" label="Telegram bot token"><Input.Password placeholder="1234:ABC…" autoComplete="new-password" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="alerts.telegram_chat_id" label="Telegram chat ID"><Input placeholder="e.g. -100123" className="mono" /></Form.Item>
            </Col>
          </Row>
          <Space>
            <Button htmlType="submit">Save</Button>
            <Button onClick={async () => { await api.post('/alerts/test', { channel: 'desktop' }); message.success('Test sent'); }}>Send test</Button>
          </Space>
        </Form>
      </Card>
      <Card size="small" className="glass" title="Settings KV store">
        <Form form={form} layout="vertical" className="form-grid" onFinish={async (v) => {
          try { await api.post('/settings', { [v.key]: v.value }); message.success('Saved'); load(); }
          catch (e) { notifyError(e); }
        }}>
          <Row gutter={[12, 0]}>
            <Col span={8}>
              <Form.Item name="key" label="Key" rules={[{ required: true, message: 'Key is required' }]}><Input placeholder="e.g. alerts.quiet_hours" className="mono" /></Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="value" label="Value" rules={[{ required: true, message: 'Value is required' }]}><Input placeholder="e.g. 22:00-08:00" className="mono" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label=" "><Button htmlType="submit">Save</Button></Form.Item>
            </Col>
          </Row>
        </Form>
        <pre style={{ fontSize: 11, marginTop: 8 }}>{JSON.stringify(kv, null, 1)}</pre>
      </Card>
    </Space>
  );
}
