'use strict';
(() => {
  const canvas = document.getElementById('matrix');
  const context = canvas.getContext('2d');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const characters = 'アカサタナハマヤラワ0123456789ABCDEFЖЗИКЛМНПРСТ#$%&';
  let columns = [], width = 0, height = 0, frame = 0, last = 0;
  function resize() {
    const scale = Math.min(devicePixelRatio || 1, 1.5);
    width = innerWidth; height = innerHeight;
    canvas.width = width * scale; canvas.height = height * scale;
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.fillStyle = '#000'; context.fillRect(0, 0, width, height);
    columns = Array.from({length: Math.ceil(width / 16)}, () => -Math.random() * height / 16);
  }
  function draw(time) {
    frame = requestAnimationFrame(draw);
    if (document.hidden || reduced.matches || time - last < 50) return;
    last = time;
    context.fillStyle = 'rgba(0,0,0,.08)'; context.fillRect(0, 0, width, height);
    context.font = '700 16px ui-monospace, Menlo, monospace';
    columns.forEach((y, i) => {
      context.fillStyle = Math.random() < .04 ? '#FFB3A8' : '#DC341E';
      context.fillText(characters[Math.floor(Math.random() * characters.length)], i * 16, y * 16);
      columns[i] = y * 16 > height && Math.random() > .975 ? 0 : y + 1;
    });
  }
  resize(); frame = requestAnimationFrame(draw);
  addEventListener('resize', resize);
  addEventListener('pagehide', () => { cancelAnimationFrame(frame); removeEventListener('resize', resize); });
})();
