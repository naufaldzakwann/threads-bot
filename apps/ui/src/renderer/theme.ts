import { theme } from 'antd';
import type { ThemeConfig } from 'antd';

/** Tema OLED futuristik THBuzzer — turunan design-system/MASTER.md (dark only). */
export const thbTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorBgBase: '#020617',
    colorBgContainer: '#0e1223',
    colorBgElevated: '#141a30',
    colorBgLayout: '#020617',
    colorBorder: '#334155',
    colorBorderSecondary: '#1e293b',
    colorTextBase: '#f8fafc',
    colorTextSecondary: '#94a3b8',
    colorPrimary: '#16a34a',
    colorSuccess: '#16a34a',
    colorWarning: '#f59e0b',
    colorError: '#dc2626',
    colorInfo: '#22d3ee',
    colorLink: '#22d3ee',
    fontFamily: "'Fira Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",
    fontFamilyCode: "'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace",
    borderRadius: 12,
    controlHeight: 34,
  },
  components: {
    Card: { colorBgContainer: 'rgba(14,18,35,0.72)', lineWidth: 1 },
    Table: { colorBgContainer: 'transparent', headerBg: 'rgba(30,41,59,0.6)', rowHoverBg: 'rgba(34,211,238,0.06)' },
    Menu: { darkItemBg: 'transparent', darkSubMenuItemBg: 'transparent', itemBorderRadius: 10 },
    Button: { borderRadius: 10 },
    Input: { colorBgContainer: '#0b1020' },
    Select: { colorBgContainer: '#0b1020' },
    Modal: { contentBg: '#0e1223', headerBg: '#0e1223' },
    Tag: { borderRadiusSM: 6 },
  },
};
