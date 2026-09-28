'use strict';
(() => {
  const canvas = document.getElementById('matrix');
  const context = canvas.getContext('2d');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const pools = globalThis.MATRIX_LINES;
  const ROW = 20, FONT = '700 13px ui-monospace, Menlo, monospace';
  const HUMOR_SHARE = 0.26, HOLD = {tech: [1500, 3000], humor: [4500, 7000], egg: [6000, 8000]}, FADE = 1500;
  const random = (min, max) => min + Math.floor(Math.random() * (max - min + 1));
  const pad = (value, size = 2) => String(value).padStart(size, '0');
  const plural = (n, one, few, many) => n % 10 === 1 && n % 100 !== 11 ? one
    : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
  const files = ['разговор.mp3', 'созвон.mp4', 'планёрка.m4a', 'интервью.wav', 'звонок_клиенту.ogg', 'встреча_2026-09-28.mp3', 'синк_по_синку.opus', 'ретро.flac'];
  const tokens = {
    n: () => random(1, 2), k: () => random(0, 3), w: () => random(1, 5),
    duration: () => `${pad(random(0, 1))}:${pad(random(12, 59))}:${pad(random(0, 59))}`,
    minutes: () => { const n = random(7, 58); return `${n} ${plural(n, 'минуту', 'минуты', 'минут')}`; },
    ts: () => `${pad(random(0, 59))}:${pad(random(0, 59))}.${pad(random(0, 999), 3)}`,
    filename: () => files[random(0, files.length - 1)],
    count: () => random(3, 64), few: () => random(0, 2), done: () => random(1, 40), total: () => random(41, 400),
    chunk: () => random(1, 40), tokens: () => random(40, 190), words: () => random(12, 900), frame: () => random(100, 9999),
    p: () => (0.5 + Math.random() / 2).toFixed(2), rtf: () => (0.05 + Math.random() / 5).toFixed(3),
    mb: () => random(900, 2600), gb: () => (2 + Math.random() * 10).toFixed(1), pid: () => random(2000, 65000),
    port: () => location.port || 18765, cpu: () => random(40, 99), patience: () => random(1, 20),
    random: () => random(0, 30), confidence: () => random(80, 99),
  };
  const fill = text => text.replace(/\{(\w+)\}/g, (match, name) => tokens[name] ? tokens[name]() : match);
  // Shuffle bags so every line appears before any repeats.
  const bags = {};
  const draw = kind => {
    if (!bags[kind]?.length) bags[kind] = pools[kind].slice().sort(() => Math.random() - .5);
    const item = bags[kind].pop();
    return (Array.isArray(item) ? item : [item]).map(fill);
  };
  let width = 0, height = 0, rows = 0, messages = [], frame = 0, last = 0, nextSpawn = 0, nextEgg = 0;

  function wrap(text, limit) {
    const lines = [];
    let line = '';
    for (const word of text.split(' ')) {
      const next = line ? `${line} ${word}` : word;
      if (line && context.measureText(next).width > limit) { lines.push(line); line = word; } else line = next;
    }
    return lines.concat(line);
  }
  // Horizontal spans of a row not hidden behind the panel.
  function freeSpans(row, panel) {
    const top = row * ROW, bottom = top + ROW, right = document.documentElement.clientWidth || width;
    if (!panel || bottom < panel.top - 4 || top > panel.bottom + 4) return [[0, right]];
    return [[0, panel.left - 12], [panel.right + 20, right]].filter(([a, b]) => b - a > 0);
  }
  // A blank row between messages keeps a series from reading into its neighbour.
  function busy(row, x0, x1) {
    return messages.some(m => m.lines.some(l => Math.abs(l.row - row) <= 1 && x0 < l.x + l.width + 24 && l.x < x1 + 24));
  }
  function place(texts, kind, now) {
    const panel = document.querySelector('main')?.getBoundingClientRect();
    for (let attempt = 0; attempt < 12; attempt++) {
      const start = random(0, rows - 1);
      const spans = freeSpans(start, panel).filter(([a, b]) => b - a >= 150);
      if (!spans.length) continue;
      const [a, b] = spans[random(0, spans.length - 1)];
      const limit = Math.min(b - a - 16, 560);
      const lines = texts.flatMap(t => wrap(t, limit)).map(text => ({text, width: context.measureText(text).width}));
      const widest = Math.max(...lines.map(l => l.width));
      const x = a + 8 + Math.random() * Math.max(0, b - a - 16 - widest);
      const fits = lines.every((l, i) => {
        const row = start + i;
        return row < rows && freeSpans(row, panel).some(([s, e]) => x >= s && x + l.width <= e) && !busy(row, x, x + l.width);
      });
      if (!fits) continue;
      const speed = kind === 'tech' ? 2 : 1;
      let at = now;
      lines.forEach((l, i) => { Object.assign(l, {row: start + i, x, start: at, speed}); at += l.text.length / speed * 50 + random(250, 650); });
      messages.push({kind, lines, fadeAt: at + random(...HOLD[kind])});
      return true;
    }
    return false;
  }
  function spawn(now) {
    const cap = Math.max(4, Math.min(16, Math.round(width * height / 80000)));
    if (messages.length >= cap) return;
    const kind = now >= nextEgg ? 'egg' : Math.random() < HUMOR_SHARE ? 'humor' : 'tech';
    context.font = FONT;
    if (place(draw(kind === 'egg' ? 'eggs' : kind), kind, now) && kind === 'egg') nextEgg = now + random(30000, 60000);
  }
  function resize() {
    const scale = Math.min(devicePixelRatio || 1, 1.5);
    width = innerWidth; height = innerHeight; rows = Math.floor(height / ROW);
    canvas.width = width * scale; canvas.height = height * scale;
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.fillStyle = '#000'; context.fillRect(0, 0, width, height);
    messages = [];
  }
  function render(time) {
    frame = requestAnimationFrame(render);
    if (document.hidden || reduced.matches || time - last < 50) return;
    last = time;
    if (!nextEgg) nextEgg = time + random(30000, 60000);
    if (time >= nextSpawn) { spawn(time); nextSpawn = time + random(250, 600); }
    messages = messages.filter(m => time < m.fadeAt + FADE);
    context.fillStyle = '#000'; context.fillRect(0, 0, width, height);
    context.font = FONT; context.textBaseline = 'middle';
    for (const m of messages) {
      context.globalAlpha = Math.max(0, Math.min(1, 1 - (time - m.fadeAt) / FADE));
      for (const l of m.lines) {
        const shown = Math.min(l.text.length, Math.floor((time - l.start) / 50 * l.speed));
        if (shown <= 0) continue;
        const y = l.row * ROW + ROW / 2, body = l.text.slice(0, shown);
        context.fillStyle = m.kind === 'egg' ? '#FFB3A8' : '#DC341E';
        context.fillText(body, l.x, y);
        if (shown < l.text.length) {
          context.fillStyle = '#FFE6E1';
          context.fillText(l.text[shown - 1], l.x + context.measureText(body.slice(0, -1)).width, y);
        }
      }
    }
    context.globalAlpha = 1;
  }
  resize(); frame = requestAnimationFrame(render);
  addEventListener('resize', resize);
  addEventListener('pagehide', () => { cancelAnimationFrame(frame); removeEventListener('resize', resize); });
})();
