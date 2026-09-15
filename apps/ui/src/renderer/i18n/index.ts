import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  id: { translation: {
    'disclaimer.risk_threads': 'Unofficial + browser automation melanggar ToS — risiko restricted/checkpoint/suspend. Kuota resmi: 250 post / 1000 reply / 500 search-mingguan. Limiter tidak bisa dimatikan.',
    'nav.dashboard': 'Dashboard', 'nav.accounts': 'Akun Threads', 'nav.proxy': 'Proxy', 'nav.growth': 'Growth',
    'nav.threads': 'Threads', 'nav.replies': 'Balasan', 'nav.campaigns': 'Kampanye', 'nav.analytics': 'Analytics',
    'nav.ai': 'AI', 'nav.settings': 'Pengaturan',
    'editor.500': '{{n}}/500 char', 'editor.link_warn': 'Maks 5 link/post',
    'quota.check': 'Cek kuota 250/1000',
  } },
  en: { translation: {
    'disclaimer.risk_threads': 'Unofficial + browser automation violates ToS — restricted/checkpoint/suspend risk. Official quotas: 250 posts / 1000 replies / 500 weekly searches. Limiter cannot be disabled.',
    'nav.dashboard': 'Dashboard', 'nav.accounts': 'Threads Accounts', 'nav.proxy': 'Proxy', 'nav.growth': 'Growth',
    'nav.threads': 'Threads', 'nav.replies': 'Replies', 'nav.campaigns': 'Campaigns', 'nav.analytics': 'Analytics',
    'nav.ai': 'AI', 'nav.settings': 'Settings',
    'editor.500': '{{n}}/500 chars', 'editor.link_warn': 'Max 5 links/post',
    'quota.check': 'Check 250/1000 quota',
  } },
};

i18n.use(initReactI18next).init({ resources, lng: 'en', fallbackLng: 'id', interpolation: { escapeValue: false } });
export default i18n;
