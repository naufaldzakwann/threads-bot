import React from 'react';
import { Button, Card, Col, Form, Input, Modal, Row, Select, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { PageHeader, StatusTag } from '../components/ui';

export default function Replies() {
  const [convs, setConvs] = React.useState<{ id: number; account_id: number; thread_id: string; unread: number }[]>([]);
  const [sel, setSel] = React.useState<number | null>(null);
  const [msgs, setMsgs] = React.useState<{ id: number; author: string; text: string; is_hidden_by_platform: number }[]>([]);
  const [rules, setRules] = React.useState<{ id: number; name: string; trigger: string; pattern: string; enabled: number }[]>([]);
  const [open, setOpen] = React.useState(false);
  const [form] = Form.useForm();
  const [reply, setReply] = React.useState('');

  const load = React.useCallback(() => {
    unwrap<{ items: never[] }>(api.get('/replies/conversations')).then((d) => setConvs(d.items as never)).catch((e) => notifyError(e));
    unwrap<{ items: never[] }>(api.get('/replies/rules')).then((d) => setRules(d.items as never)).catch(() => undefined);
  }, []);
  React.useEffect(load, [load]);
  const loadMsgs = (cid: number) => {
    setSel(cid);
    unwrap<{ items: never[] }>(api.get(`/replies/conversations/${cid}/messages`)).then((d) => setMsgs(d.items as never)).catch((e) => notifyError(e));
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <PageHeader title="Replies Inbox" sub="mentions · auto-reply rules · mass replies (no DMs on Threads)" />
      <Row gutter={12} align="stretch">
        <Col span={6}>
          <Card size="small" className="glass" title={`Threads (${convs.length})`} styles={{ body: { maxHeight: 460, overflowY: 'auto' } }}>{convs.map((c) => (
            <div key={c.id} onClick={() => loadMsgs(c.id)} style={{ padding: 6, cursor: 'pointer', background: sel === c.id ? '#e6f4ff' : undefined }}>
              <Tag color={c.unread ? 'red' : 'default'}>{c.unread ? 'new' : 'read'}</Tag> {c.thread_id || `conv-${c.id}`} <span style={{ color: '#999' }}>account {c.account_id}</span>
            </div>))}
            {convs.length === 0 && <span style={{ color: '#999' }}>Empty — polled every 15 min.</span>}</Card>
        </Col>
        <Col span={10}>
          <Card size="small" className="glass" title="Replies" styles={{ body: { maxHeight: 460, overflowY: 'auto' } }}>
            {msgs.map((m) => <div key={m.id} style={{ marginBottom: 6 }}><b>{m.author}:</b> {m.text} {m.is_hidden_by_platform ? <StatusTag status="hidden_by_platform" /> : null}</div>)}
            {sel && (
              <Space.Compact style={{ width: '100%', marginTop: 8 }}>
                <Input value={reply} onChange={(e) => setReply(e.target.value.slice(0, 500))} placeholder="Reply ≤500 chars" />
                <Button type="primary" onClick={async () => {
                  try {
                    const c = convs.find((x) => x.id === sel);
                    await api.post('/replies/send', { account_id: c?.account_id, thread_id: c?.thread_id, text: reply });
                    message.success('Reply queued (high priority)'); setReply(''); loadMsgs(sel);
                  } catch (e) { notifyError(e); }
                }}>Send</Button>
              </Space.Compact>)}
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" className="glass" title={`Auto-reply rules (${rules.length})`} styles={{ body: { maxHeight: 460, overflowY: 'auto' } }} extra={<Button size="small" type="primary" onClick={() => setOpen(true)}>Add</Button>}>
            {rules.map((r) => <div key={r.id} style={{ marginBottom: 4 }}><Tag>{r.trigger}</Tag> {r.name} <code style={{ fontSize: 11 }}>{r.pattern}</code>
              <Button size="small" type="link" danger onClick={async () => { await api.del(`/replies/rules/${r.id}`); load(); }}>delete</Button></div>)}
          </Card>
        </Col>
      </Row>
      <Modal open={open} title="New rule" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={async (v) => {
          try { await api.post('/replies/rules', { ...v, response_template: v.template }); message.success('Rule created'); setOpen(false); form.resetFields(); load(); }
          catch (e) { notifyError(e); }
        }}>
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Name is required' }]}><Input /></Form.Item>
          <Form.Item name="trigger" label="Trigger" initialValue="keyword"><Select options={['keyword', 'regex', 'any', 'first_reply', 'mention', 'quote', 'new_follower'].map((t) => ({ value: t }))} /></Form.Item>
          <Form.Item name="pattern" label="Keyword / regex"><Input /></Form.Item>
          <Form.Item name="template" label="Template (spintax)"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
