import React from 'react';
import { Button, Card, Col, Form, Input, Row, Select, Space, Table, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { accountIdRule, idListRule, parseIdList } from '../api/validators';
import { PageHeader, Panel, StatusTag, W } from '../components/ui';
import { useTranslation } from 'react-i18next';

const REPLY_CONTROLS = ['everyone', 'accounts_you_follow', 'mentioned_only', 'parent_post_author_only', 'followers_only'];

export default function Threads() {
  const { t } = useTranslation();
  const [text, setText] = React.useState('');
  const [queue, setQueue] = React.useState<{ id: number; type: string; account_id: number; status: string; scheduled_at: number }[]>([]);
  const [list, setList] = React.useState<{ id: number; account_id: number; status: string; topic_tag: string }[]>([]);
  const [form] = Form.useForm();
  const links = (text.match(/https?:\/\/\S+/g) || []).length;

  const load = React.useCallback(() => {
    unwrap<{ items: never[] }>(api.get('/threads-posts/queue-24h')).then((d) => setQueue(d.items as never)).catch(() => undefined);
    unwrap<{ items: never[] }>(api.get('/threads-posts')).then((d) => setList(d.items as never)).catch((e) => notifyError(e));
  }, []);
  React.useEffect(load, [load]);
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { const r = await fn(); message.success(ok); load(); return r; } catch (e) { notifyError(e); }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <PageHeader title="Threads Posting" sub="scheduler · threadstorms · media validation" />
      <Card size="small" className="glass" title="Quick thread">
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/threads-posts/quick-thread', { account_ids: parseIdList(v.accounts || ''), text }), 'Scheduled')}>
          <Form.Item name="accounts" label="Account IDs (comma — e.g. 1,2,3)" rules={[{ required: true, message: 'At least 1 account ID is required' }, idListRule('Account IDs')]}><Input placeholder="1,2,3" /></Form.Item>
          <Input.TextArea rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a thread ≤500 chars — the first #tag becomes the topic tag" />
          <div>{t('editor.500', { n: text.length })} {text.length > 500 && <b style={{ color: 'red' }}>E-VALID-TEXT-LIMIT</b>} · {links}/5 links {links > 5 && <b style={{ color: 'red' }}>{t('editor.link_warn')}</b>}</div>
          <Form.Item style={{ marginTop: 8 }}><Button type="primary" htmlType="submit" disabled={!text || text.length > 500 || links > 5}>Schedule (staggered 1–8 min/account)</Button></Form.Item>
        </Form>
      </Card>
      <Card size="small" className="glass" title="Threadstorm (>500 chars, linear chain)">
        <Threadstorm onDone={load} />
      </Card>
      <Panel title="24-hour queue" count={queue.length}>
        <Table size="small" rowKey="id" dataSource={queue} pagination={{ pageSize: 10, showSizeChanger: false }}
          columns={[{ title: 'Job', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Type', dataIndex: 'type', width: W.type, className: 'mono', ellipsis: true },
            { title: 'Account', dataIndex: 'account_id', width: W.account, align: 'center' as const, className: 'num' },
            { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
            { title: 'Scheduled', dataIndex: 'scheduled_at', width: W.time, render: (v: number) => new Date(v * 1000).toLocaleString('en-US') }]} />
      </Panel>
      <Panel title="Scheduled threads" count={list.length}>
        <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 10, showSizeChanger: false }}
          columns={[{ title: 'ID', dataIndex: 'id', width: W.id, className: 'mono' }, { title: 'Account', dataIndex: 'account_id', width: W.account, align: 'center' as const, className: 'num' },
            { title: 'Tag', dataIndex: 'topic_tag', width: W.tag, ellipsis: true, className: 'mono' },
            { title: 'Status', dataIndex: 'status', width: W.status, render: (s: string) => <StatusTag status={s} /> },
            { title: 'Actions', width: 120, align: 'right' as const, render: (_: unknown, r: { id: number }) => <Button size="small" danger onClick={() => act(() => api.post(`/threads-posts/${r.id}/cancel`), 'Cancelled')}>Cancel</Button> }]} />
      </Panel>
      <Card size="small" className="glass" title="Media validation (§9.1)">
        <MediaCheck />
      </Card>
    </Space>
  );
}

function Threadstorm({ onDone }: { onDone: () => void }) {
  const [f] = Form.useForm();
  return (
    <Form form={f} layout="vertical" onFinish={async (v) => {
      try {
        const r = await unwrap<{ parts: number }>(api.post('/threads-posts/threadstorm', { account_id: Number(v.account_id), text: v.text, reply_control: v.reply_control || 'everyone' }));
        message.success(`Split into ${r.parts} segments`); onDone(); f.resetFields();
      } catch (e) { notifyError(e); }
    }}>
      <Row gutter={[12, 0]}>
        <Col span={8}>
          <Form.Item name="account_id" label="Account ID" rules={[{ required: true, message: 'Account ID is required' }, accountIdRule()]}><Input type="number" min={1} placeholder="e.g. 3" /></Form.Item>
        </Col>
        <Col span={16}>
          <Form.Item name="reply_control" label="Who can reply" initialValue="everyone"><Select options={REPLY_CONTROLS.map((r) => ({ value: r }))} /></Form.Item>
        </Col>
      </Row>
      <Form.Item name="text" rules={[{ required: true, message: 'Text is required' }]}><Input.TextArea rows={4} placeholder="Long text — auto-split per 500 chars at sentence boundaries" /></Form.Item>
      <Button type="primary" htmlType="submit">Create threadstorm</Button>
    </Form>
  );
}

function MediaCheck() {
  const [f] = Form.useForm();
  const [out, setOut] = React.useState('');
  return (
    <Form form={f} layout="vertical" className="form-grid" onFinish={async (v) => {
      try {
        const r = await unwrap<{ via: string }>(api.post('/threads-posts/media/validate', { kind: v.kind, width: Number(v.width) || 0, height: Number(v.height) || 0, size_bytes: Number(v.size) || 0, duration_sec: Number(v.dur) || 0 }));
        setOut(`OK via ${r.via}`);
      } catch (e) { setOut(String(e)); }
    }}>
      <Row gutter={[12, 0]}>
        <Col span={4}>
          <Form.Item name="kind" label="Kind" initialValue="image"><Select options={[{ value: 'image' }, { value: 'video' }]} /></Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item name="width" label="Width (px)"><Input type="number" min={0} placeholder="1080" /></Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item name="height" label="Height (px)"><Input type="number" min={0} placeholder="1080" /></Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item name="size" label="Size (bytes)"><Input type="number" min={0} placeholder="500000" /></Form.Item>
        </Col>
        <Col span={5}>
          <Form.Item name="dur" label="Duration s (video)"><Input type="number" min={0} placeholder="60" /></Form.Item>
        </Col>
      </Row>
      <Space>
        <Button htmlType="submit">Check</Button>
        <span className="mono" style={{ fontSize: 12 }}>{out}</span>
      </Space>
    </Form>
  );
}
