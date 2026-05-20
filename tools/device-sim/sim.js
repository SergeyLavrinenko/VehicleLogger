#!/usr/bin/env node
// Симулятор ESP32: шлёт POST /api/telemetry и /api/device/ping
// в формате Communication.md / docs/api.html.
//
// Два режима:
//   1) Интерактивный (по умолчанию, если нет --once): консоль с командами.
//   2) CLI: --once / --interval / --anomaly и т.д.
//
// Примеры:
//   node sim.js                              # интерактивный режим
//   node sim.js --once                       # один пакет и выход
//   node sim.js --interval=2000 --anomaly=overheat
//   node sim.js --device=VL-A3F82B02 --key=dev-key-002

const readline = require('node:readline');

const args = Object.fromEntries(
  process.argv.slice(2)
    .filter(a => a.startsWith('--'))
    .map(a => {
      const [k, v] = a.slice(2).split('=');
      return [k, v ?? true];
    })
);

const cfg = {
  url:      args.url      || 'https://nonconf.ru',
  device:   args.device   || 'VL-A3F82B01',
  key:      args.key      || 'dev-key-001',
  interval: parseInt(args.interval || '5000', 10),
  pingEvery: parseInt(args['ping-every'] || '6', 10),
  anomaly:  args.anomaly  || 'none'
};

const state = {
  rpm: 1700,
  speed: 70,
  coolantTemp: 88,
  oilPressure: 3.3,
  fuelLevel: 80,
  voltage: 13.8,
  iter: 0
};

let timerId = null;
let running = false;
let totalSent = 0;
let totalErr  = 0;

function drift(value, range, min, max) {
  const next = value + (Math.random() - 0.5) * range;
  return Math.min(max, Math.max(min, next));
}

function nextSample() {
  state.rpm         = drift(state.rpm,         200, 800,  3500);
  state.speed       = drift(state.speed,       8,   0,    120);
  state.coolantTemp = drift(state.coolantTemp, 1.5, 70,   100);
  state.oilPressure = drift(state.oilPressure, 0.2, 2.0,  4.5);
  state.fuelLevel   = Math.max(0, state.fuelLevel - 0.05);
  state.voltage     = drift(state.voltage,     0.1, 12.5, 14.5);

  const data = {
    rpm:         Math.round(state.rpm),
    speed:       +state.speed.toFixed(1),
    coolantTemp: +state.coolantTemp.toFixed(1),
    oilPressure: +state.oilPressure.toFixed(2),
    fuelLevel:   Math.round(state.fuelLevel),
    voltage:     +state.voltage.toFixed(2),
    dtcCodes:    []
  };

  switch (cfg.anomaly) {
    case 'overheat':
      data.coolantTemp = +(105 + Math.random() * 3).toFixed(1); break;
    case 'oilpressure':
      data.oilPressure = +(1.1 + Math.random() * 0.2).toFixed(2); break;
    case 'dtc':
      data.dtcCodes = ['P0301', 'P0217']; break;
  }
  return data;
}

async function postJson(path, body) {
  const res = await fetch(`${cfg.url}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Device-Key': cfg.key
    },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  return { status: res.status, body: text };
}

function ts() { return new Date().toLocaleTimeString(); }

async function sendTelemetry() {
  const data = nextSample();
  const payload = { deviceId: cfg.device, timestamp: new Date().toISOString(), data };
  try {
    const r = await postJson('/api/telemetry', payload);
    if (r.status === 200) totalSent++; else totalErr++;
    const tag = r.status === 200 ? 'OK ' : 'ERR';
    console.log(
      `[${ts()}] ${tag} ${r.status}  ` +
      `rpm=${data.rpm} spd=${data.speed} cool=${data.coolantTemp}°C ` +
      `oil=${data.oilPressure}bar fuel=${data.fuelLevel}% v=${data.voltage}V` +
      (data.dtcCodes.length ? ` dtc=${data.dtcCodes.join(',')}` : '') +
      (r.status !== 200 ? `  → ${r.body.slice(0, 120)}` : '')
    );
  } catch (e) {
    totalErr++;
    console.error(`[${ts()}] FAIL ${e.message}`);
  }
}

async function sendPing() {
  try {
    const r = await postJson('/api/device/ping', { deviceId: cfg.device });
    console.log(`[${ts()}] PING ${r.status}`);
  } catch (e) {
    console.error(`[${ts()}] PING FAIL ${e.message}`);
  }
}

async function tick() {
  state.iter++;
  await sendTelemetry();
  if (state.iter % cfg.pingEvery === 0) await sendPing();
}

function start() {
  if (running) { console.log('уже идёт'); return; }
  running = true;
  console.log(`▶ старт: ${cfg.url} device=${cfg.device} interval=${cfg.interval}ms anomaly=${cfg.anomaly}`);
  tick();
  timerId = setInterval(tick, cfg.interval);
}

function stop() {
  if (!running) { console.log('не запущено'); return; }
  clearInterval(timerId);
  timerId = null;
  running = false;
  console.log(`⏸ стоп. отправлено: ${totalSent}, ошибок: ${totalErr}`);
}

function showStatus() {
  console.log('--- состояние ---');
  console.log(`url:      ${cfg.url}`);
  console.log(`device:   ${cfg.device}`);
  console.log(`key:      ${cfg.key}`);
  console.log(`interval: ${cfg.interval}ms`);
  console.log(`anomaly:  ${cfg.anomaly}`);
  console.log(`running:  ${running ? 'да' : 'нет'}`);
  console.log(`отправлено: ${totalSent}, ошибок: ${totalErr}`);
}

function help() {
  console.log(`
команды:
  s, start              запустить цикл отправки
  x, stop               остановить цикл
  send                  отправить один пакет
  ping                  отправить один heartbeat
  a, anomaly <тип>      none | overheat | oilpressure | dtc
  i, interval <ms>      сменить интервал отправки
  d, device <serial>    сменить deviceId (например VL-A3F82B02)
  k, key <api-key>      сменить X-Device-Key
  u, url <url>          сменить адрес бэкенда
  status                текущее состояние
  reset                 сбросить накопленные стейты (rpm, fuel и т.д.)
  h, help               эта справка
  q, quit, exit         выход
`);
}

function resetState() {
  state.rpm = 1700; state.speed = 70; state.coolantTemp = 88;
  state.oilPressure = 3.3; state.fuelLevel = 80; state.voltage = 13.8;
  state.iter = 0;
  console.log('состояние сброшено');
}

async function handleCommand(line) {
  const parts = line.trim().split(/\s+/);
  const cmd = (parts[0] || '').toLowerCase();
  const arg = parts.slice(1).join(' ');

  switch (cmd) {
    case '': return;
    case 's': case 'start':    start(); break;
    case 'x': case 'stop':     stop(); break;
    case 'send':               await sendTelemetry(); break;
    case 'ping':               await sendPing(); break;
    case 'a': case 'anomaly': {
      const t = (arg || 'none').toLowerCase();
      if (!['none', 'overheat', 'oilpressure', 'dtc'].includes(t)) {
        console.log('тип: none | overheat | oilpressure | dtc');
      } else {
        cfg.anomaly = t;
        console.log(`anomaly = ${t}`);
      }
      break;
    }
    case 'i': case 'interval': {
      const ms = parseInt(arg, 10);
      if (!ms || ms < 100) { console.log('нужен ms >= 100'); break; }
      cfg.interval = ms;
      if (running) { stop(); start(); }
      console.log(`interval = ${ms}ms`);
      break;
    }
    case 'd': case 'device':
      if (!arg) { console.log('нужно: device VL-...'); break; }
      cfg.device = arg; console.log(`device = ${arg}`); break;
    case 'k': case 'key':
      if (!arg) { console.log('нужно: key dev-key-...'); break; }
      cfg.key = arg; console.log(`key = ${arg}`); break;
    case 'u': case 'url':
      if (!arg) { console.log('нужно: url http://...'); break; }
      cfg.url = arg.replace(/\/$/, ''); console.log(`url = ${cfg.url}`); break;
    case 'status':             showStatus(); break;
    case 'reset':              resetState(); break;
    case 'h': case 'help': case '?': help(); break;
    case 'q': case 'quit': case 'exit':
      if (running) stop();
      console.log('пока');
      process.exit(0);
    default:
      console.log(`неизвестная команда: ${cmd}. напиши "help"`);
  }
}

// --- Точка входа ---

(async () => {
  console.log('device-sim — симулятор ESP32 для VehicleLogger');
  showStatus();

  if (args.once) {
    await sendPing();
    await sendTelemetry();
    process.exit(0);
  }

  // если переданы CLI-аргументы кроме --device/--key/--url — стартуем цикл сразу
  if (args.interval || args.anomaly) {
    start();
  } else {
    console.log('\nнапиши "start" чтобы погнать поток, "help" — список команд.\n');
  }

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: '> '
  });
  rl.prompt();
  rl.on('line', async (line) => {
    await handleCommand(line);
    rl.prompt();
  });
  rl.on('close', () => {
    if (running) stop();
    process.exit(0);
  });
})();
