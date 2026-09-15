import React from 'react';
import { Button, Card, Form, Input, Select, Space, Table, Tag, message } from 'antd';
import { api, notifyError, unwrap } from '../api/client';
import { accountIdRule, idListRule, parseIdList } from '../api/validators';
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
      <Card size="small" className="glass" title="Quick thread">
        <Form form={form} layout="vertical" onFinish={(v) => act(() => api.post('/threads-posts/quick-thread', { account_ids: parseIdList(v.accounts || ''), text }), 'dijadwalkan')}>
          <Form.Item name="accounts" label="Account ID (koma — cth 1,2,3)" rules={[{ required: true }, idListRule('Account ID')]}><Input placeholder="1,2,3" /></Form.Item>
          <Input.TextArea rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="Tulis utas ≤500 char, #tag pertama jadi topic_tag" />
          <div>{t('editor.500', { n: text.length })} {text.length > 500 && <b style={{ color: 'red' }}>E-VALID-TEXT-LIMIT</b>} · {links}/5 link {links > 5 && <b style={{ color: 'red' }}>{t('editor.link_warn')}</b>}</div>
          <Form.Item style={{ marginTop: 8 }}><Button type="primary" htmlType="submit" disabled={!text || text.length > 500 || links > 5}>Jadwalkan (stagger 1–8 mnt/akun)</Button></Form.Item>
        </Form>
      </Card>
      <Card size="small" className="glass" title="Threadstorm (>500 char, rantai linear)">
        <Threadstorm onDone={load} />
      </Card>
      <Card size="small" className="glass" title="Antrean 24 jam">
        <Table size="small" rowKey="id" dataSource={queue} pagination={{ pageSize: 10 }}
          columns={[{ title: 'Job', dataIndex: 'id' }, { title: 'Tipe', dataIndex: 'type' }, { title: 'Akun', dataIndex: 'account_id' },
            { title: 'Status', dataIndex: 'status', render: (s: string) => <Tag>{s}</Tag> },
            { title: 'Jadwal', dataIndex: 'scheduled_at', render: (v: number) => new Date(v * 1000).toLocaleString('id-ID') }]} />
      </Card>
      <Card size="small" className="glass" title="Threads terjadwal">
        <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 10 }}
          columns={[{ title: 'ID', dataIndex: 'id' }, { title: 'Akun', dataIndex: 'account_id' },
            { title: 'Tag', dataIndex: 'topic_tag' },
            { title: 'Status', dataIndex: 'status', render: (s: string) => <Tag color={s === 'published' ? 'green' : 'default'}>{s}</Tag> },
            { title: 'Aksi', render: (_: unknown, r: { id: number }) => <Button size="small" danger onClick={() => act(() => api.post(`/threads-posts/${r.id}/cancel`), 'dibatalkan')}>Batal</Button> }]} />
      </Card>
      <Card size="small" className="glass" title="Validasi media (§9.1)">
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
        message.success(`terpecah ${r.parts} segmen`); onDone(); f.resetFields();
      } catch (e) { notifyError(e); }
    }}>
      <Space style={{ width: '100%' }} align="start">
        <Form.Item name="account_id" rules={[{ required: true }, accountIdRule()]}><Input type="number" min={1} placeholder="Account ID" style={{ width: 140 }} /></Form.Item>
        <Form.Item name="reply_control" initialValue="everyone"><Select style={{ width: 200 }} options={REPLY_CONTROLS.map((r) => ({ value: r }))} /></Form.Item>
      </Space>
      <Form.Item name="text" rules={[{ required: true }]}><Input.TextArea rows={4} placeholder="Teks panjang — otomatis dipecah per 500 char antar-kalimat" /></Form.Item>
      <Button type="primary" htmlType="submit">Buat threadstorm</Button>
    </Form>
  );
}

function MediaCheck() {
  const [f] = Form.useForm();
  const [out, setOut] = React.useState('');
  return (
    <Form form={f} layout="inline" onFinish={async (v) => {
      try {
        const r = await unwrap<{ via: string }>(api.post('/threads-posts/media/validate', { kind: v.kind, width: Number(v.width) || 0, height: Number(v.height) || 0, size_bytes: Number(v.size) || 0, duration_sec: Number(v.dur) || 0 }));
        setOut(`OK via ${r.via}`);
      } catch (e) { setOut(String(e)); }
    }}>
      <Form.Item name="kind" initialValue="image"><Select style={{ width: 110 }} options={[{ value: 'image' }, { value: 'video' }]} /></Form.Item>
      <Form.Item name="width"><Input placeholder="lebar px" style={{ width: 110 }} /></Form.Item>
      <Form.Item name="height"><Input placeholder="tinggi px" style={{ width: 110 }} /></Form.Item>
      <Form.Item name="size"><Input placeholder="byte" style={{ width: 130 }} /></Form.Item>
      <Form.Item name="dur"><Input placeholder="detik (video)" style={{ width: 130 }} /></Form.Item>
      <Form.Item><Button htmlType="submit">Cek</Button></Form.Item>
      <span>{out}</span>
    </Form>
  );
}
