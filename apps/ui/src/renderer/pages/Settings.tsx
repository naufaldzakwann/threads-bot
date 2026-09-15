import React from 'react';
import { Button, Card, Form, Input, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { accountIdRule, httpUrlRule } from '../api/validators';

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
      <Card size="small" className="glass" title="Info backend"><pre style={{ fontSize: 11 }}>{JSON.stringify(info, null, 1)}</pre>
        <Space>
          <Button danger size="small" onClick={async () => { await api.post('/system/killswitch', { scope: 'global', on: true }); message.warning('KILL global aktif'); }}>KILL global</Button>
          <Button size="small" onClick={async () => { await api.post('/system/killswitch', { scope: 'global', on: false }); message.success('scheduler resume'); }}>Resume</Button>
        </Space></Card>
      <Card size="small" className="glass" title="OAuth Threads (tier brand_official)">
        <Form form={oauth} layout="inline" onFinish={async (v) => {
          try {
            const r = await unwrap<{ authorize_url: string }>(api.post('/engines/oauth/start', { app_id: v.app_id, redirect_uri: v.redirect, scopes: undefined }));
            message.info('Buka URL ini, salin code, lalu Tukar code di bawah.');
            (document.getElementById('oauth-url') as HTMLAnchorElement | null)?.setAttribute('href', r.authorize_url);
          } catch (e) { notifyError(e); }
        }}>
          <Form.Item name="app_id" rules={[{ required: true }]}><Input placeholder="App ID" /></Form.Item>
          <Form.Item name="redirect" rules={[{ required: true }, httpUrlRule('Redirect URI')]}><Input placeholder="Redirect URI" style={{ width: 260 }} className="mono" /></Form.Item>
          <Form.Item><Button htmlType="submit">Buat authorize URL</Button></Form.Item>
          <a id="oauth-url" target="_blank" rel="noreferrer">authorize →</a>
        </Form>
        <Form layout="inline" style={{ marginTop: 8 }} onFinish={async (v) => {
          try {
            const r = await unwrap<{ token_id: number }>(api.post('/engines/oauth/callback', { ...v, account_id: Number(v.account_id) }));
            message.success(`token tersimpan #${r.token_id}`); load();
          } catch (e) { notifyError(e); }
        }}>
          <Form.Item name="account_id" rules={[{ required: true }, accountIdRule()]}><Input type="number" min={1} placeholder="Account ID" /></Form.Item>
          <Form.Item name="code" rules={[{ required: true }]}><Input placeholder="code" style={{ width: 200 }} /></Form.Item>
          <Form.Item name="app_id" rules={[{ required: true }]}><Input placeholder="App ID" /></Form.Item>
          <Form.Item name="app_secret" rules={[{ required: true }]}><Input.Password placeholder="App Secret" /></Form.Item>
          <Form.Item name="redirect_uri" rules={[{ required: true }, httpUrlRule('Redirect URI')]}><Input placeholder="Redirect URI" style={{ width: 220 }} className="mono" /></Form.Item>
          <Form.Item><Button type="primary" htmlType="submit">Tukar code → token</Button></Form.Item>
        </Form>
        <Table size="small" rowKey="id" dataSource={tokens} pagination={false} style={{ marginTop: 8 }}
          columns={[{ title: 'Akun', dataIndex: 'account_id' }, { title: 'Sisa hari', dataIndex: 'days_left' },
            { title: 'Aksi', render: (_: unknown, r: { id: number }) => (
              <Space><Button size="small" onClick={async () => { try { await api.post(`/engines/threads-tokens/${r.id}/test`); message.success('token valid'); } catch (e) { notifyError(e); } }}>Test</Button>
                <Button size="small" onClick={async () => { try { await api.post(`/engines/threads-tokens/${r.id}/refresh`, {}); message.success('direfresh'); load(); } catch (e) { notifyError(e); } }}>Refresh</Button></Space>) }]} />
      </Card>
      <Card size="small" className="glass" title="Alert (desktop + webhook + Telegram)">
        <Form form={alertForm} layout="inline" onFinish={async (v) => {
          try { await api.post('/alerts/settings', v); message.success('alert disimpan'); }
          catch (e) { notifyError(e); }
        }}>
          <Form.Item name="alerts.webhook_url" rules={[httpUrlRule('Webhook URL')]}><Input placeholder="Webhook JSON URL" style={{ width: 260 }} className="mono" /></Form.Item>
          <Form.Item name="alerts.telegram_bot_token"><Input.Password placeholder="Telegram bot token" style={{ width: 220 }} /></Form.Item>
          <Form.Item name="alerts.telegram_chat_id"><Input placeholder="Chat ID" style={{ width: 140 }} /></Form.Item>
          <Form.Item><Button htmlType="submit">Simpan</Button></Form.Item>
          <Button onClick={async () => { await api.post('/alerts/test', { channel: 'desktop' }); message.success('test terkirim'); }}>Test</Button>
        </Form>
      </Card>
      <Card size="small" className="glass" title="Settings KV">
        <Form form={form} layout="inline" onFinish={async (v) => {
          try { await api.post('/settings', { [v.key]: v.value }); message.success('disimpan'); load(); }
          catch (e) { notifyError(e); }
        }}>
          <Form.Item name="key" rules={[{ required: true }]}><Input placeholder="key" /></Form.Item>
          <Form.Item name="value" rules={[{ required: true }]}><Input placeholder="value" style={{ width: 300 }} /></Form.Item>
          <Form.Item><Button htmlType="submit">Simpan</Button></Form.Item>
        </Form>
        <pre style={{ fontSize: 11, marginTop: 8 }}>{JSON.stringify(kv, null, 1)}</pre>
      </Card>
    </Space>
  );
}
