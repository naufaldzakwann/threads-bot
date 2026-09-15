// Main process: spawn thbuzzer-core --headless, handshake THBUZZER_READY, tray, watchdog (§3.1).
import { app, BrowserWindow, Tray, Menu, Notification, dialog } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import path from 'path';

let win: BrowserWindow | null = null;
let core: ChildProcess | null = null;
let restarts = 0;
export let CORE_INFO: { port: number; token: string } | null = null;

const CORE_BIN = process.env.THBUZZER_CORE || path.join(process.resourcesPath, 'thbuzzer-core.exe');

function spawnCore() {
  core = spawn(CORE_BIN, ['--headless'], { env: { ...process.env, THBUZZER_PARENT_PID: String(process.pid) } });
  let buf = '';
  core.stdout?.on('data', (d) => {
    buf += d.toString();
    const line = buf.split('\n').find((l) => l.includes('THBUZZER_READY'));
    if (line) {
      try {
        const payload = JSON.parse(line.slice(line.indexOf('{')));
        CORE_INFO = { port: payload.port, token: payload.token };
        win?.webContents.send('core-ready', CORE_INFO);
      } catch { /* filter token dari log */ }
    }
  });
  core.on('exit', () => {
    // Watchdog backoff 1s/5s/30s maks 5x (§3.1)
    if (restarts < 5) {
      const wait = [1000, 5000, 30000][Math.min(restarts, 2)];
      restarts++;
      setTimeout(spawnCore, wait);
    } else {
      dialog.showErrorBox('THBuzzer', 'Backend gagal start 5x. Cek logs.');
    }
  });
}

function createWindow() {
  win = new BrowserWindow({ width: 1400, height: 900,
    webPreferences: { contextIsolation: true, sandbox: true, preload: path.join(__dirname, '../preload/index.js') } });
  if (process.env.VITE_DEV) win.loadURL('http://127.0.0.1:5173');
  else win.loadFile(path.join(__dirname, '../renderer/index.html'));
  win.on('close', (e) => { // X -> tray (§17)
    e.preventDefault();
    win?.hide();
  });
}

app.whenReady().then(() => {
  // Dialog first-run Penggunaan Bertanggung Jawab (§2.3) disederhanakan di renderer.
  spawnCore();
  createWindow();
  const iconPath = path.join(__dirname, '../../resources/icons/icon.png');
  if (fs.existsSync(iconPath)) {
  const tray = new Tray(iconPath);
  tray.setToolTip('THBuzzer — antrean 0');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Tampilkan', click: () => win?.show() },
    { label: 'Pause scheduler', click: () => win?.webContents.send('kill', { scope: 'global', on: true }) },
    { label: 'Resume', click: () => win?.webContents.send('kill', { scope: 'global', on: false }) },
    { label: 'Quit', click: async () => {
      try { await fetch(`http://127.0.0.1:${CORE_INFO?.port}/system/shutdown`, { method: 'POST', headers: { Authorization: `Bearer ${CORE_INFO?.token}` } }); } catch {}
      setTimeout(() => app.exit(0), 15000);
    } },
  ]));
  }
  // Kill switch Ctrl+Shift+X (§14)
  win?.webContents.on('before-input-event', (_e, input) => {
    if (input.control && input.shift && input.key.toLowerCase() === 'x') win?.webContents.send('kill', { scope: 'global', on: true });
  });
});
app.on('window-all-closed', () => {});
