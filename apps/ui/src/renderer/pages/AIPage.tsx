import React from 'react';
import { Button, Card, Col, Form, Input, Modal, Row, Select, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { intRule } from '../api/validators';
import { PageHeader, Panel, W } from '../components/ui';

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
      <PageHeader title="AI Studio" sub="OpenAI-compatible profiles · personas · stance-tuned generation" />
      <Card size="small" className="glass" title="LLM profiles (OpenAI-compatible)" extra={<Button size="small" type="primary" onClick={() => setOpen(true)}>Add</Button>}>
        <Table size="small" rowKey="id" dataSource={profs} pagination={false}
          columns={[{ title: 'Name', dataIndex: 'name', width: 220, ellipsis: true }, { title: 'Model', dataIndex: 'model', ellipsis: true, className: 'mono' }]} />
        <div style={{ marginTop: 8 }}>Personas: {personas.map((p) => p.name).join(', ') || '–'}
          <Button size="small" type="link" onClick={async () => {
            const name = prompt('Persona name:'); if (name) { await api.post('/ai/personas', { name, spec: {} }); load(); }
          }}>+ persona</Button></div>
      </Card>
      <Card size="small" className="glass" title="Generation playground (stance 60/20/10/10)">
        <Form form={gen} layout="vertical" className="form-grid" onFinish={async (v) => {
          try {
            const r = await unwrap<{ text: string; fallback?: string }>(api.post('/ai/generate', { profile_id: Number(v.pid) || 0, kind: v.kind || 'reply', context: v.context, stance: v.stance || 'mendukung' }));
            setOut(r.text + (r.fallback ? ' [template fallback: AI disabled]' : ''));
          } catch (e) { notifyError(e); }
        }}>
          <Row gutter={[12, 0]}>
            <Col span={6}>
              <Form.Item name="kind" label="Kind" initialValue="reply"><Select options={['reply', 'quote_rewrite', 'thread_caption', 'campaign_reply'].map((k) => ({ value: k }))} /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="stance" label="Stance" initialValue="mendukung"><Select options={['mendukung', 'kepo', 'testimonial', 'reply_komentar_lain'].map((k) => ({ value: k }))} /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="pid" label="Profile ID (0 = fallback)" rules={[intRule('Profile ID', 0, 2147483647)]}><Input type="number" min={0} placeholder="0" /></Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="context" label="Context" rules={[{ required: true, message: 'Context is required' }]}><Input placeholder="e.g. viral thread about…" /></Form.Item>
            </Col>
          </Row>
          <Button type="primary" htmlType="submit">Generate</Button>
        </Form>
        {out && <pre style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{out}</pre>}
      </Card>
      <Card size="small" className="glass" title="Prompt templates (editable)">
        <Input.TextArea rows={4} value={prompts} onChange={(e) => setPrompts(e.target.value)} className="mono" />
        <Button style={{ marginTop: 8 }} onClick={async () => {
          try { await api.post('/ai/prompts', JSON.parse(prompts || '{}')); message.success('Prompts saved'); }
          catch (e) { notifyError(e); }
        }}>Save</Button>
      </Card>
      <Modal open={open} title="LLM profile" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={async (v) => {
          try { await api.post('/ai/profiles', v); message.success('Profile created'); setOpen(false); form.resetFields(); load(); }
          catch (e) { notifyError(e); }
        }}>
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Name is required' }]}><Input /></Form.Item>
          <Form.Item name="base_url" label="Base URL" initialValue="https://api.openai.com/v1"><Input className="mono" /></Form.Item>
          <Form.Item name="model" label="Model" initialValue="gpt-4o-mini"><Input className="mono" /></Form.Item>
          <Form.Item name="api_key" label="API key (optional)"><Input.Password autoComplete="new-password" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
