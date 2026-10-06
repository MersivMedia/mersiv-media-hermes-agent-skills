/* site.js — motion-site runtime. Reads site.json + assets/frames.json, builds the page, and scrubs each
   section's frame sequence on a sticky canvas as you scroll (Lenis smooth scroll + GSAP ScrollTrigger).
   No build step: gsap, ScrollTrigger and lenis are vendored in ./vendor.
   window.__site = { ready, progress, sections, seek(sectionIndex, p) } for headless QA. */
(async () => {
  const $ = (s, el = document) => el.querySelector(s);
  const h = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  window.__site = { ready: false, progress: 0, sections: [] };

  const [site, frames] = await Promise.all([fetch('site.json').then(r => r.json()), fetch('assets/frames.json').then(r => r.json()).catch(() => ({}))]);
  const root = document.documentElement;
  for (const [k, v] of Object.entries(site.brand?.vars ?? {})) root.style.setProperty('--' + k, v);
  if (site.brand?.fonts_css) { const l = h('link'); l.rel = 'stylesheet'; l.href = site.brand.fonts_css; document.head.appendChild(l); }
  document.title = site.title ?? site.brand?.name ?? 'Motion site';
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const mobile = matchMedia('(max-width: 720px)').matches;

  // nav
  const nav = h('nav', 'nav');
  nav.append(site.brand?.logo ? Object.assign(h('img', 'logo'), { src: site.brand.logo, alt: site.brand.name }) :
    Object.assign(h('a', 'wordmark', esc(site.brand?.name)), { href: '#' }));
  if (site.cta) nav.append(Object.assign(h('a', 'cta', esc(site.cta.label)), { href: site.cta.href }));
  document.body.append(nav, h('div', 'grain'));
  const loader = h('div', 'loader', '<div class="bar"><i></i></div>');
  document.body.append(loader);

  // sections
  const main = h('main');
  document.body.append(main);
  const scenes = [];
  for (const s of site.sections) {
    if (s.type === 'block') {   // plain HTML section (pricing, proof, faq, contact)
      const b = h('section', 'block');
      b.id = s.id;
      b.innerHTML = s.html ?? `${s.eyebrow ? `<p class="eyebrow">${esc(s.eyebrow)}</p>` : ''}<h2 class="h2">${esc(s.title)}</h2>` +
        (s.body ? `<p class="lede">${esc(s.body)}</p>` : '') +
        (s.cards ? `<div class="cards">${s.cards.map(c => `<div class="card"><b>${esc(c.big)}</b><span>${esc(c.small)}</span></div>`).join('')}</div>` : '') +
        (s.button ? `<a class="btn" href="${esc(s.button.href)}">${esc(s.button.label)} →</a>` : '') +
        (s.note ? `<p class="example-note">${esc(s.note)}</p>` : '');
      main.append(b);
      continue;
    }
    // "mobile_clip": "<id>_m" swaps in a phone-only clip (e.g. 9:16) on phones; same section, same copy.
    const vid = (mobile && s.mobile_clip && frames[s.mobile_clip]) ? s.mobile_clip : s.id;
    const f = frames[vid];
    const sec = h('section', 'scene');
    sec.id = s.id;
    sec.style.setProperty('--len', s.length ?? 300);           // scroll pacing: vh of scroll per clip
    const stage = h('div', 'stage');
    const poster = Object.assign(h('img', 'poster'), { src: `assets/posters/${vid}.webp`, alt: '' });
    const canvas = h('canvas');
    stage.append(poster, canvas, h('div', 'tint'), h('div', 'vignette'));
    if (s.particles && !reduce) stage.append(h('canvas', 'particles'));
    const cls = `copy ${s.align ?? ''}`;
    const lines = (s.title ?? '').split('\n').map(l => `<span class="line"><span>${esc(l)}</span></span>`).join('');
    const tag = s.id === site.sections[0].id ? 'h1' : 'h2';
    const copy = h('div', cls, (s.eyebrow ? `<p class="eyebrow">${esc(s.eyebrow)}</p>` : '') + `<${tag} class="${tag}">${lines}</${tag}>` +
      (s.body ? `<p class="lede">${esc(s.body)}</p>` : '') +
      (s.cards ? `<div class="cards">${s.cards.map(c => `<div class="card"><b>${esc(c.big)}</b><span>${esc(c.small)}</span></div>`).join('')}</div>` : '') +
      (s.button ? `<a class="btn" href="${esc(s.button.href)}">${esc(s.button.label)} →</a>` : ''));
    stage.append(copy);
    sec.append(stage);
    main.append(sec);
    scenes.push({ s, f, vid, sec, stage, canvas, poster, copy, imgs: [], loaded: 0, drawn: -1 });
  }
  const foot = h('footer', 'footer', `<span>© ${new Date().getFullYear()} ${esc(site.brand?.name)}</span><span>${esc(site.footer ?? '')}</span>`);
  document.body.append(foot);
  window.__site.sections = scenes.map(x => x.s.id);

  // frame loading: posters show instantly; sequences load section by section (first section first)
  const pick = n => `f${String(n).padStart(4, '0')}.webp`;
  const bar = $('.bar i', loader);
  const totalFrames = scenes.reduce((a, x) => a + (x.f?.count ?? 0), 0) || 1;
  let loadedFrames = 0;
  function loadScene(x) {
    if (!x.f || reduce) return Promise.resolve();
    const dir = `assets/frames/${x.vid}/${mobile ? 'm/' : ''}`;
    return Promise.all(Array.from({ length: x.f.count }, (_, i) => new Promise(res => {
      const im = new Image();
      im.decoding = 'async';
      im.onload = im.onerror = () => { x.loaded++; loadedFrames++; window.__site.progress = loadedFrames / totalFrames; if (bar) bar.style.width = `${window.__site.progress * 100}%`; res(); };
      im.src = dir + pick(i + 1);
      x.imgs[i] = im;
    })));
  }
  await loadScene(scenes[0]);                     // first section gates the loader
  gsap.to(loader, { autoAlpha: 0, duration: .6, onComplete: () => loader.remove() });
  (async () => { for (const x of scenes.slice(1)) await loadScene(x); })();

  // draw: cover-fit the frame into the canvas (DPR-aware)
  function draw(x, idx) {
    const im = x.imgs[idx];
    if (!im || !im.complete || !im.naturalWidth) return;
    const c = x.canvas, dpr = Math.min(devicePixelRatio || 1, 2);
    const W = c.clientWidth * dpr, H = c.clientHeight * dpr;
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; x.drawn = -1; }
    if (x.drawn === idx) return;
    // fit: "cover" (default, fills the screen, crops) or "contain" (whole frame visible, page bg around it).
    // "fit_mobile": "contain" shows a wide (21:9) clip edge to edge on a phone instead of a crop.
    // focus: [fx, fy] 0..1 = where the frame sits (cover: which part survives the crop; contain: where the
    // letterboxed frame sits). "focus_mobile" overrides on portrait screens.
    const port = W < H;
    const fit = (port && x.s.fit_mobile) || x.s.fit || 'cover';
    const s = (fit === 'contain' ? Math.min : Math.max)(W / im.naturalWidth, H / im.naturalHeight);
    const w = im.naturalWidth * s, hh = im.naturalHeight * s;
    const fc = (port && x.s.focus_mobile) || x.s.focus || [0.5, 0.5];
    const g = c.getContext('2d');
    if (fit === 'contain') { g.fillStyle = getComputedStyle(document.body).backgroundColor || '#000'; g.fillRect(0, 0, W, H); }
    g.imageSmoothingQuality = 'high';
    g.drawImage(im, (W - w) * fc[0], (H - hh) * fc[1], w, hh);
    // edge_fade: {"side":"left","solid":.17,"fade":.28,"color":"#030303"} paints the frame's edge to a solid
    // page colour (fractions of the FRAME width), so a dark edge with AI noise / dim figures reads as clean black
    // and merges with the letterbox. Covers any letterbox on that side too.
    // edge_fade_mobile overrides on portrait screens (null = none), e.g. when a phone-only clip has its own dark area
    const ef = (port && 'edge_fade_mobile' in x.s) ? x.s.edge_fade_mobile : x.s.edge_fade;
    if (ef && (ef.side === 'top' || ef.side === 'bottom')) {
      // vertical version: solid band from the frame's top (or bottom) edge, then a fade (fractions of FRAME height)
      const dy = (H - hh) * fc[1], col = ef.color || '#000000', top = ef.side === 'top';
      const y0 = top ? dy : dy + hh, d = top ? 1 : -1;
      const ys = y0 + d * hh * (ef.solid ?? .15), ye = y0 + d * hh * (ef.fade ?? .3);
      const gr = g.createLinearGradient(0, y0, 0, ye);
      gr.addColorStop(0, col); gr.addColorStop(Math.abs(ys - y0) / Math.abs(ye - y0), col); gr.addColorStop(1, col + '00');
      g.fillStyle = gr;
      g.fillRect(0, top ? 0 : ye, W, top ? ye : H - ye);
    } else if (ef) {
      const dx = (W - w) * fc[0], dy = (H - hh) * fc[1], col = ef.color || '#000000';
      const x0 = ef.side === 'right' ? dx + w : dx, dir = ef.side === 'right' ? -1 : 1;
      const xs = x0 + dir * w * (ef.solid ?? .15), xe = x0 + dir * w * (ef.fade ?? .3);
      const gr = g.createLinearGradient(x0, 0, xe, 0);
      gr.addColorStop(0, col); gr.addColorStop(Math.abs(xs - x0) / Math.abs(xe - x0), col); gr.addColorStop(1, col + '00');
      g.fillStyle = gr;
      const left = dir > 0 ? 0 : xe, right = dir > 0 ? xe : W;
      g.fillRect(left, Math.max(0, dy), right - left, Math.min(H, dy + hh) - Math.max(0, dy));
    }
    if (!x.posterFit) {   // keep the poster (shown before frames decode) framed exactly like the canvas
      x.posterFit = 1;
      x.poster.style.objectFit = fit;
      x.poster.style.objectPosition = `${fc[0] * 100}% ${fc[1] * 100}%`;
    }
    x.drawn = idx;
    if (x.poster.style.opacity !== '0') x.poster.style.opacity = '0';
  }

  // smooth scroll + scroll triggers
  const lenis = new Lenis({ lerp: site.pacing?.lerp ?? 0.085, smoothWheel: true });
  window.__lenis = lenis;
  lenis.on('scroll', ScrollTrigger.update);
  gsap.ticker.add(t => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
  gsap.registerPlugin(ScrollTrigger);

  for (const x of scenes) {
    const st = { p: 0 };
    x.st = ScrollTrigger.create({
      trigger: x.sec, start: 'top top', end: 'bottom bottom', scrub: site.pacing?.scrub ?? 0.6,
      onUpdate: self => { st.p = self.progress; if (x.f) draw(x, Math.min(x.f.count - 1, Math.round(self.progress * (x.f.count - 1)))); },
    });
    x.progress = () => st.p;
    // copy reveal: lines rise in as the section arrives, fade before it leaves
    const lines = x.copy.querySelectorAll('.line > span');
    gsap.fromTo(lines, { yPercent: 110 }, { yPercent: 0, stagger: .08, ease: 'power3.out', duration: 1,
      scrollTrigger: { trigger: x.sec, start: 'top 70%', toggleActions: 'play none none reverse' } });
    gsap.fromTo(x.copy.querySelectorAll('.eyebrow, .lede, .cards, .btn'), { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, stagger: .08, duration: .9,
      ease: 'power2.out', scrollTrigger: { trigger: x.sec, start: 'top 60%', toggleActions: 'play none none reverse' } });
    gsap.to(x.copy, { autoAlpha: 0, y: -40, ease: 'none', scrollTrigger: { trigger: x.sec, start: 'bottom 140%', end: 'bottom 100%', scrub: true } });
    // first frame: draw now if decoded, else on load. addEventListener, NOT .onload =, which would replace the
    // loader's counter handler and stall every later section's frames (caught by qa.mjs: last section STATIC).
    if (x.f && x.imgs[0]) x.imgs[0].complete ? draw(x, 0) : x.imgs[0].addEventListener('load', () => draw(x, 0), { once: true });
  }
  addEventListener('resize', () => scenes.forEach(x => { x.drawn = -1; if (x.f) draw(x, Math.round(x.progress() * (x.f.count - 1))); }));

  // particles: drifting dust motes, seeded, one small canvas per stage that asks for them
  for (const x of scenes) {
    const pc = x.stage.querySelector('canvas.particles');
    if (!pc) continue;
    let seed = 7 + x.s.id.length;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const N = mobile ? 40 : 90;
    const P = Array.from({ length: N }, () => ({ x: rnd(), y: rnd(), r: .4 + rnd() * 1.8, v: .02 + rnd() * .06, a: .15 + rnd() * .5 }));
    const g = pc.getContext('2d');
    gsap.ticker.add((t) => {
      const W = pc.clientWidth, H = pc.clientHeight;
      if (pc.width !== W) { pc.width = W; pc.height = H; }
      g.clearRect(0, 0, W, H);
      g.fillStyle = x.s.particles === true ? 'rgba(255,255,255,1)' : x.s.particles;
      for (const p of P) {
        const y = ((p.y - t * p.v * .1) % 1 + 1) % 1, xx = p.x + Math.sin(t * .3 + p.y * 9) * .01;
        g.globalAlpha = p.a; g.beginPath(); g.arc(xx * W, y * H, p.r, 0, 6.283); g.fill();
      }
      g.globalAlpha = 1;
    });
  }

  // QA hook: jump to section i at progress p (used by qa.mjs; immediate, no smoothing)
  window.__site.seek = (i, p) => {
    const x = scenes[i];
    const y = x.sec.offsetTop + p * (x.sec.offsetHeight - innerHeight);
    lenis.scrollTo(y, { immediate: true, force: true });
    ScrollTrigger.update();
    if (x.f) { x.drawn = -1; draw(x, Math.min(x.f.count - 1, Math.round(p * (x.f.count - 1)))); }
  };
  window.__site.ready = true;
})().catch(e => { console.error('site.js', e); window.__site = { ...(window.__site || {}), error: String(e) }; });
