import React from 'react';
import { Button, Card, Form, Input, Modal, Select, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { intRule } from '../api/validators';

export default function AIPage() {
  const [profs, setProfs] = React.useState<{ id: number; name: string; model: string }[]>([]);
  const [personas, setPersonas] = React.useState<{ id: number; name: string }[]>([]);
  const [prompts, setPrompts] = React.useState('{}');
  const [out, setOut] = React.useState('');
  const [open, setOpen] = React.useState(false);
  const [form] = Form.useForm();
  const [gen] = Form.useForm();

  const load = React.useCallback(() => {
    unwrap<{ items: never[] }>(api.get('/ai/profiles')).then((d) => setProfs(d.items as never)).catch((e) => notifyError(e));
    unwrap<{ items: never[] }>(api.get('/ai/personas')).then((d) => setPersonas(d.items as never)).catch(() => undefined);
    unwrap<Record<string, string>>(api.get('/ai/prompts')).then((d) => setPrompts(JSON.stringify(d, null, 1))).catch(() => undefined);
  }, []);
  React.useEffect(load, [load]);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Card size="small" className="glass" title="Profil LLM (OpenAI-compatible)" extra={<Button size="small" type="primary" onClick={() => setOpen(true)}>Tambah</Button>}>
        <Table size="small" rowKey="id" dataSource={profs} pagination={false}
          columns={[{ title: 'Nama', dataIndex: 'name' }, { title: 'Model', dataIndex: 'model' }]} />
        <div style={{ marginTop: 8 }}>Persona: {personas.map((p) => p.name).join(', ') || '-'}
          <Button size="small" type="link" onClick={async () => {
            const name = prompt('Nama persona:'); if (name) { await api.post('/ai/personas', { name, spec: {} }); load(); }
          }}>+ persona</Button></div>
      </Card>
      <Card size="small" className="glass" title="Generate tester (stance 60/20/10/10)">
        <Form form={gen} layout="inline" onFinish={async (v) => {
          try {
            const r = await unwrap<{ text: string; fallback?: string }>(api.post('/ai/generate', { profile_id: Number(v.pid) || 0, kind: v.kind || 'reply', context: v.context, stance: v.stance || 'mendukung' }));
            setOut(r.text + (r.fallback ? ' [template-fallback: AI nonaktif]' : ''));
          } catch (e) { notifyError(e); }
        }}>
          <Form.Item name="pid" rules={[intRule('Profile ID', 0, 2147483647)]}><Input type="number" min={0} placeholder="profile ID (0=fallback)" style={{ width: 190 }} /></Form.Item>
          <Form.Item name="kind" initialValue="reply"><Select style={{ width: 150 }} options={['reply', 'quote_rewrite', 'thread_caption', 'campaign_reply'].map((k) => ({ value: k }))} /></Form.Item>
          <Form.Item name="stance" initialValue="mendukung"><Select style={{ width: 170 }} options={['mendukung', 'kepo', 'testimonial', 'reply_komentar_lain'].map((k) => ({ value: k }))} /></Form.Item>
          <Form.Item name="context" rules={[{ required: true }]}><Input placeholder="konteks" style={{ width: 220 }} /></Form.Item>
          <Form.Item><Button type="primary" htmlType="submit">Generate</Button></Form.Item>
        </Form>
        {out && <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{out}</pre>}
      </Card>
      <Card size="small" className="glass" title="Prompt template (editable)">
        <Input.TextArea rows={4} value={prompts} onChange={(e) => setPrompts(e.target.value)} />
        <Button style={{ marginTop: 8 }} onClick={async () => {
          try { await api.post('/ai/prompts', JSON.parse(prompts || '{}')); message.success('prompt disimpan'); }
          catch (e) { notifyError(e); }
        }}>Simpan</Button>
      </Card>
      <Modal open={open} title="Profil LLM" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={async (v) => {
          try { await api.post('/ai/profiles', v); message.success('profil dibuat'); setOpen(false); form.resetFields(); load(); }
          catch (e) { notifyError(e); }
        }}>
          <Form.Item name="name" label="Nama" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="base_url" label="Base URL" initialValue="https://api.openai.com/v1"><Input /></Form.Item>
          <Form.Item name="model" label="Model" initialValue="gpt-4o-mini"><Input /></Form.Item>
          <Form.Item name="api_key" label="API key (opsional)"><Input.Password /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
