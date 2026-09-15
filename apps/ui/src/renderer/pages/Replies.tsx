import React from 'react';
import { Button, Card, Col, Form, Input, Modal, Row, Select, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';

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
      <Row gutter={12}>
        <Col span={7}>
          <Card size="small" className="glass" title="Utas">{convs.map((c) => (
            <div key={c.id} onClick={() => loadMsgs(c.id)} style={{ padding: 6, cursor: 'pointer', background: sel === c.id ? '#e6f4ff' : undefined }}>
              <Tag color={c.unread ? 'red' : 'default'}>{c.unread ? 'baru' : 'dibaca'}</Tag> {c.thread_id || `conv-${c.id}`} <span style={{ color: '#999' }}>akun {c.account_id}</span>
            </div>))}
            {convs.length === 0 && <span style={{ color: '#999' }}>Kosong — polling tiap 15 mnt.</span>}</Card>
        </Col>
        <Col span={9}>
          <Card size="small" className="glass" title="Balasan">
            {msgs.map((m) => <div key={m.id} style={{ marginBottom: 6 }}><b>{m.author}:</b> {m.text} {m.is_hidden_by_platform ? <Tag color="red">hidden_by_platform</Tag> : null}</div>)}
            {sel && (
              <Space.Compact style={{ width: '100%', marginTop: 8 }}>
                <Input value={reply} onChange={(e) => setReply(e.target.value.slice(0, 500))} placeholder="Balas ≤500 char" />
                <Button type="primary" onClick={async () => {
                  try {
                    const c = convs.find((x) => x.id === sel);
                    await api.post('/replies/send', { account_id: c?.account_id, thread_id: c?.thread_id, text: reply });
                    message.success('reply diantre (prioritas high)'); setReply(''); loadMsgs(sel);
                  } catch (e) { notifyError(e); }
                }}>Kirim</Button>
              </Space.Compact>)}
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" className="glass" title="Rules auto-reply" extra={<Button size="small" type="primary" onClick={() => setOpen(true)}>Tambah</Button>}>
            {rules.map((r) => <div key={r.id} style={{ marginBottom: 4 }}><Tag>{r.trigger}</Tag> {r.name} <code style={{ fontSize: 11 }}>{r.pattern}</code>
              <Button size="small" type="link" danger onClick={async () => { await api.del(`/replies/rules/${r.id}`); load(); }}>hapus</Button></div>)}
          </Card>
        </Col>
      </Row>
      <Modal open={open} title="Rule baru" onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={async (v) => {
          try { await api.post('/replies/rules', { ...v, response_template: v.template }); message.success('rule dibuat'); setOpen(false); form.resetFields(); load(); }
          catch (e) { notifyError(e); }
        }}>
          <Form.Item name="name" label="Nama" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="trigger" label="Trigger" initialValue="keyword"><Select options={['keyword', 'regex', 'any', 'first_reply', 'mention', 'quote', 'new_follower'].map((t) => ({ value: t }))} /></Form.Item>
          <Form.Item name="pattern" label="Keyword/regex"><Input /></Form.Item>
          <Form.Item name="template" label="Template (spintax)"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
