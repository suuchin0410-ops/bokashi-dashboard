/* 前回の様子（第 2 回 in 岩内）特設ページの動き（GSAP 3.15.0）
   決まり: 21_GSAP.md（power3.out / expo.out・移動 16〜24px・弾まない・matchMedia で「減らす」設定を分ける）
   React Bits の考え方を素の JS に書き直し: 「Blur Text」（ぼやけた字にピントが合う・表紙と各場面の動詞 = この頁の見せ場）
   「Scroll Expand」（表紙の写真が少し引いて収まる）「Count Up」（数字）「Scroll Velocity」（帯）
   https://reactbits.dev/ — Copyright (c) David Haz — MIT + Commons Clause（部品単体の再配布・販売は禁止）
   JS が止まっても全部見える（gsap.from を基本にする） */
(function () {
  if (!window.gsap || !window.ScrollTrigger) return;
  gsap.registerPlugin(ScrollTrigger);
  document.documentElement.classList.add('js-motion');
  var mm = gsap.matchMedia();

  function splitChars(el) {
    var out = [];
    (function walk(node, parent) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var frag = document.createDocumentFragment();
          n.textContent.split('').forEach(function (c) {
            var sp = document.createElement('span'); sp.className = 'ch'; sp.textContent = c; frag.appendChild(sp); out.push(sp);
          });
          parent.replaceChild(frag, n);
        } else if (n.nodeType === 1 && n.tagName === 'BR') { /* 改行はそのまま */ }
        else if (n.nodeType === 1) { walk(n, n); }
      });
    })(el, el);
    return out;
  }

  mm.add('(prefers-reduced-motion: no-preference)', function () {
    var ease = 'power3.out';

    /* 読み進みの線 */
    gsap.to('.progress', { scaleX: 1, ease: 'none', scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: 0.3 } });

    /* 1. 表紙: 写真が少し引いて収まり、題が 1 文字ずつピントを結ぶ（この頁の見せ場） */
    var h1 = document.querySelector('.cover h1');
    var chars = h1 ? splitChars(h1) : [];
    var tl = gsap.timeline({ defaults: { ease: ease } });
    tl.from('.cover .bg img', { scale: 1.18, duration: 2.0, ease: 'expo.out' }, 0)
      .from('.cover .kicker', { opacity: 0, y: 16, duration: 0.6 }, 0.1)
      .from(chars, { opacity: 0, y: 28, filter: 'blur(14px)', duration: 0.9, ease: 'power4.out', stagger: 0.045 }, 0.2)
      .from('.cover .sub', { opacity: 0, y: 16, duration: 0.7 }, 0.9)
      .from('.hint', { opacity: 0, duration: 0.6 }, 1.2);
    gsap.to('.cover .bg img', { yPercent: 14, ease: 'none', scrollTrigger: { trigger: '.cover', start: 'top top', end: 'bottom top', scrub: true } });
    gsap.to('.cover .in', { opacity: 0, y: -24, ease: 'none', scrollTrigger: { trigger: '.cover', start: '40% top', end: 'bottom top', scrub: true } });

    /* 2. 数字が回る（最後は必ず元の表記） */
    gsap.utils.toArray('.count').forEach(function (el) {
      var to = parseInt(el.getAttribute('data-to'), 10), final = el.textContent, obj = { v: 0 };
      gsap.to(obj, { v: to, duration: 1.2, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 88%', once: true },
        onUpdate: function () { el.textContent = Math.round(obj.v); }, onComplete: function () { el.textContent = final; } });
    });
    gsap.from('.stat', { opacity: 0, y: 18, duration: 0.6, ease: ease, stagger: 0.08, scrollTrigger: { trigger: '.stats', start: 'top 85%', once: true } });

    /* 3. 場面: 写真はゆっくり流れ（視差）、動詞がピントを結び、説明と事実が続く。差し込み写真は少し傾いた状態から収まる */
    gsap.utils.toArray('.scene').forEach(function (sc) {
      var img = sc.querySelector('.bg img');
      gsap.fromTo(img, { yPercent: -8 }, { yPercent: 8, ease: 'none', scrollTrigger: { trigger: sc, start: 'top bottom', end: 'bottom top', scrub: true } });
      var verb = sc.querySelector('.verb');
      var vchars = verb ? splitChars(verb) : [];
      var t = gsap.timeline({ scrollTrigger: { trigger: sc, start: 'top 62%', once: true } });
      t.from(sc.querySelector('.no'), { opacity: 0, x: -24, duration: 0.8, ease: ease }, 0)
       .from(sc.querySelector('.daytag'), { opacity: 0, y: 12, duration: 0.5, ease: ease }, 0)
       .from(vchars, { opacity: 0, y: 36, filter: 'blur(12px)', duration: 0.8, ease: 'power4.out', stagger: 0.06 }, 0.05)
       .from(sc.querySelector('.cap'), { opacity: 0, y: 18, duration: 0.7, ease: ease }, 0.45)
       .from(sc.querySelectorAll('.facts li'), { opacity: 0, y: 14, duration: 0.5, ease: ease, stagger: 0.07 }, 0.6);
      var inset = sc.querySelector('.inset');
      if (inset) t.from(inset, { opacity: 0, scale: 0.86, rotation: 4, transformOrigin: '50% 50%', duration: 0.9, ease: 'expo.out' }, 0.3);
    });

    /* 4. 帯: スクロールが速いほど速く流れ、止まると戻る */
    var track = document.querySelector('.marquee-track');
    if (track) {
      var loop = gsap.to(track, { xPercent: -50, duration: 40, ease: 'none', repeat: -1 });
      var target = 1;
      ScrollTrigger.create({ onUpdate: function (self) { target = 1 + Math.min(Math.abs(self.getVelocity()) / 350, 5); } });
      gsap.ticker.add(function () { loop.timeScale(gsap.utils.interpolate(loop.timeScale(), target, 0.08)); target += (1 - target) * 0.04; });
    }

    /* 5. そして、余市へ: 半島マークが塗られ、題がピントを結ぶ */
    var fin = document.querySelector('.fin');
    if (fin) {
      var fh = fin.querySelector('h2');
      var fchars = fh ? splitChars(fh) : [];
      var ft = gsap.timeline({ scrollTrigger: { trigger: fin, start: 'top 60%', once: true } });
      ft.from('.fin .big .fill', { scaleX: 0, duration: 1.1, ease: 'expo.out' }, 0)
        .from('.fin .big .line', { strokeDashoffset: 100, duration: 1.2, ease: 'power2.inOut' }, 0.05)
        .from(fchars, { opacity: 0, y: 30, filter: 'blur(12px)', duration: 0.9, ease: 'power4.out', stagger: 0.05 }, 0.15)
        .from('.fin .date', { opacity: 0, y: 16, duration: 0.6, ease: ease }, 0.7)
        .from('.fin .btn', { opacity: 0, y: 16, duration: 0.5, ease: ease, stagger: 0.08 }, 0.85)
        .from('.fin .src', { opacity: 0, duration: 0.6 }, 1.0);
    }

    window.addEventListener('load', function () { ScrollTrigger.refresh(); });
  });

  /* PC だけ: 主ボタンが指先に少し寄る */
  mm.add('(prefers-reduced-motion: no-preference) and (hover: hover) and (pointer: fine)', function () {
    document.querySelectorAll('.btn-primary').forEach(function (btn) {
      var xTo = gsap.quickTo(btn, 'x', { duration: 0.3, ease: 'power2.out' }), yTo = gsap.quickTo(btn, 'y', { duration: 0.3, ease: 'power2.out' });
      btn.addEventListener('mousemove', function (e) { var r = btn.getBoundingClientRect(); xTo(((e.clientX - r.left) / r.width - 0.5) * 12); yTo(((e.clientY - r.top) / r.height - 0.5) * 8); });
      btn.addEventListener('mouseleave', function () { xTo(0); yTo(0); });
    });
  });
})();
