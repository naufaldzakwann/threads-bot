import React from 'react';
import { Button, ConfigProvider, Input, Layout, Menu, message } from 'antd';
import {
  AimOutlined, ApiOutlined, DashboardOutlined, ExperimentOutlined, MessageOutlined,
  RocketOutlined, SendOutlined, SettingOutlined, TeamOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { autoConnect, connectWS, setConnection } from '../api/client';
import { thbTheme } from '../theme';
import Dashboard from './Dashboard';
import Accounts from './Accounts';
import Proxies from './Proxies';
import Growth from './Growth';
import Threads from './Threads';
import Replies from './Replies';
import Campaigns from './Campaigns';
import Analytics from './Analytics';
import AIPage from './AIPage';
import Settings from './Settings';

const NAV = [
  { key: 'dashboard', icon: <DashboardOutlined /> },
  { key: 'accounts', icon: <TeamOutlined /> },
  { key: 'proxy', icon: <ApiOutlined /> },
  { key: 'growth', icon: <ThunderboltOutlined /> },
  { key: 'threads', icon: <SendOutlined /> },
  { key: 'replies', icon: <MessageOutlined /> },
  { key: 'campaigns', icon: <RocketOutlined /> },
  { key: 'analytics', icon: <AimOutlined /> },
  { key: 'ai', icon: <ExperimentOutlined /> },
  { key: 'settings', icon: <SettingOutlined /> },
] as const;

type Ev = { event: string } & Record<string, unknown>;

export default function App() {
  const { t } = useTranslation();
  const [page, setPage] = React.useState<string>('dashboard');
  const [agreed, setAgreed] = React.useState(false);
  const [base, setBase] = React.useState(localStorage.getItem('thb.base') || 'http://127.0.0.1:8899');
  const [token, setToken] = React.useState(localStorage.getItem('thb.token') || '');
  const [connected, setConnected] = React.useState<'probing' | 'online' | 'manual'>('probing');
  const [feed, setFeed] = React.useState<Ev[]>([]);

  // Auto-connect on boot + re-probe every 10s while offline
  // (backend restart → new port/token → recovers by itself, no clicks needed)
  const connectedRef = React.useRef(connected);
  connectedRef.current = connected;
  React.useEffect(() => {
    let stop = false;
    const probe = async (silent: boolean) => {
      const { base: b, token: tok, auto } = await autoConnect();
      if (stop) return;
      if (auto) {
        setBase(b);
        setToken(tok);
        if (connectedRef.current !== 'online') {
          setConnected('online');
          if (!silent) message.success(`Connected to core ${b}`);
        }
      } else if (!silent) {
        setConnected('manual');
      }
    };
    probe(false);
    const t = setInterval(() => {
      if (connectedRef.current !== 'online') probe(true);
    }, 10000);
    return () => { stop = true; clearInterval(t); };
  }, []);

  React.useEffect(() => {
    if (connected !== 'online' || !token) return;
    const ws = connectWS((e) => {
      setFeed((f) => [...f.slice(-99), e]);
      if (e.event === 'alert.raised') message.warning(`[${String(e.kind)}] ${String(e.message)}`);
    });
    return () => ws.close();
  }, [connected, token, base]);

  const save = () => {
    setConnection(base, token);
    setConnected('online');
    message.success('Connection saved');
  };

  return (
    <ConfigProvider theme={thbTheme}>
      <Layout className="thb-shell">
        <Layout.Sider theme="dark" width={208} style={{ background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(14px)', borderRight: '1px solid #1e293b' }}>
          <div style={{ padding: '18px 18px 14px' }}>
            <div className="thb-logo">THBuzzer</div>
            <div className="thb-logo-sub">threads ops console</div>
          </div>
          <Menu theme="dark" selectedKeys={[page]} onClick={(e) => setPage(e.key)}
            items={NAV.map((n) => ({ key: n.key, icon: n.icon, label: t(`nav.${n.key}`) }))} />
          <div style={{ padding: 18, marginTop: 8, color: '#64748b', fontSize: 11 }} className="mono">
            {connected === 'online' ? <span><span className="live-dot" /> core online</span>
              : connected === 'probing' ? 'contacting core…' : 'manual mode — enter connection'}
          </div>
        </Layout.Sider>
        <Layout style={{ padding: 16, background: 'transparent' }}>
          <div className="glass" style={{ display: 'flex', gap: 8, marginBottom: 14, padding: '10px 14px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span className={connected === 'online' ? 'live-dot' : undefined}
              style={connected === 'online' ? undefined : { display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#f59e0b' }} />
            <Input value={base} onChange={(e) => setBase(e.target.value)} style={{ width: 230 }} className="mono" aria-label="Core base URL" />
            <Input.Password value={token} onChange={(e) => setToken(e.target.value)} placeholder="Bearer token (from the THBUZZER_READY log line)" style={{ maxWidth: 380 }} className="mono" aria-label="Bearer token" />
            <Button type="primary" onClick={save}>Connect</Button>
            <span style={{ color: '#64748b', fontSize: 11 }}>auto via connection.json while the backend is running</span>
          </div>
          {!agreed && (
            <div className="glass" style={{ padding: 12, marginBottom: 14, borderColor: '#f59e0b' }}>
              <span style={{ fontSize: 12 }}>{t('disclaimer.risk_threads')}</span>
              <label style={{ marginLeft: 12, fontSize: 12 }}><input type="checkbox" onChange={(e) => setAgreed(e.target.checked)} /> I understand the risks</label>
            </div>
          )}
          <Layout.Content style={{ background: 'transparent' }}>
            {page === 'dashboard' && <Dashboard feed={feed} connected={connected === 'online'} />}
            {page === 'accounts' && <Accounts />}
            {page === 'proxy' && <Proxies />}
            {page === 'growth' && <Growth />}
            {page === 'threads' && <Threads />}
            {page === 'replies' && <Replies />}
            {page === 'campaigns' && <Campaigns />}
            {page === 'analytics' && <Analytics />}
            {page === 'ai' && <AIPage />}
            {page === 'settings' && <Settings />}
          </Layout.Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}
