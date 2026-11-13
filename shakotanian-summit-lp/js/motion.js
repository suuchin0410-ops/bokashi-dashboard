/* シャコタニアンサミット 3 in 余市 — 動き（GSAP 3.15.0）
   決まり: Projects/design/21_GSAP.md「動きの基本セット」+ 23_HUMAN_DESIGN.md 5（見せ場は最初の 1 か所）+ 12_REACT_BITS.md（素の HTML に書き直し）
   1 最初の画面の登場（半島マークが塗られながら線が描かれる → 一言 → 日付 → 見出しを 1 文字ずつ【ページで唯一の大きな見せ場】→ リード → ボタン → 注記・合計 1.2 秒）
   2 数字のカウントアップ 3 半島マークがスクロールで沈む（scrub）・丸いバッジがスクロールで回る
   4 節の見出しが行ごとに下から現れる・英字の一言・表の行が順に 5 写真が幕のように開き、スクロールで枠いっぱいに広がる（Scroll Expand）
   6 ブランドの演出: 町の名前の帯がスクロールの速さで加速（Scroll Velocity）・日付のパタパタ板（Split Flap Text）・ボタンの印が反転（CSS）
   7 PC だけボタンが指先に寄る
   「視差効果を減らす」設定では何も動かさない（帯も CSS 側で止まる）。JS が止まっても全部見える（gsap.from を基本にする）

   React Bits「Split Flap Text」https://reactbits.dev/text-animations/split-flap-text ・「Scroll Velocity」https://reactbits.dev/text-animations/scroll-velocity
   Copyright (c) David Haz — MIT + Commons Clause（部品単体の再配布・販売は禁止）。考え方だけを素の JS に書き直し、色と文字はうちの値 */
(function () {
  if (!window.gsap || !window.ScrollTrigger) return;
  gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
  document.documentElement.classList.add('js-motion');

  var mm = gsap.matchMedia();

  /* 見出しの行（.nb）を枡（.ln）で包む。下から出すときに枡の外は見えない */
  function wrapLines(sel) {
    document.querySelectorAll(sel).forEach(function (h) {
      h.querySelectorAll(':scope > .nb').forEach(function (nb) {
        if (nb.parentElement.classList.contains('ln')) return;
        var ln = document.createElement('span'); ln.className = 'ln';
        nb.parentNode.insertBefore(ln, nb); ln.appendChild(nb);
      });
    });
  }
  /* 見出しを 1 文字ずつに分ける（見せ場の 1 か所だけ）。.h（青い 1 文字）はそのまま 1 つの字として残す */
  function splitChars(el) {
    var out = [];
    function walk(node, parent) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var frag = document.createDocumentFragment();
          n.textContent.split('').forEach(function (c) {
            var sp = document.createElement('span'); sp.className = 'ch'; sp.textContent = c; frag.appendChild(sp); out.push(sp);
          });
          parent.replaceChild(frag, n);
        } else if (n.nodeType === 1 && n.classList.contains('h')) {
          n.classList.add('ch'); out.push(n);
        } else if (n.nodeType === 1) { walk(n, n); }
      });
    }
    walk(el, el);
    return out;
  }

  mm.add('(prefers-reduced-motion: no-preference)', function () {
    var ease = 'power3.out';
    var h1 = document.querySelector('.hero h1');
    var chars = h1 ? splitChars(h1) : [];
    wrapLines('main .section h2, .footer .tag');

    /* 1. 最初の画面（合計 1.2 秒）。見せ場: 見出しが 1 文字ずつ、少し大きく・少し傾いた状態から落ちて揃う */
    var tl = gsap.timeline({ defaults: { ease: ease } });
    tl.from('.hero-mark .fill', { scaleX: 0, transformOrigin: '100% 50%', duration: 1.0, ease: 'expo.out' }, 0)
      .from('.hero-mark .line', { strokeDashoffset: 100, duration: 1.1, ease: 'power2.inOut' }, 0.05)
      .from('.hero .one', { opacity: 0, y: 16, duration: 0.5 }, 0.05)
      .from('.hero .date', { opacity: 0, y: 16, duration: 0.5 }, 0.12)
      .from(chars, { opacity: 0, y: 56, scale: 1.35, rotation: -5, transformOrigin: '50% 100%', duration: 0.65, ease: 'power4.out', stagger: 0.04 }, 0.2)
      .from('.hero .lead', { opacity: 0, y: 16, duration: 0.6 }, 0.55)
      .from('.hero .btn-row .btn', { opacity: 0, y: 16, duration: 0.5, stagger: 0.08 }, 0.65)
      .from('.hero .btn-note', { opacity: 0, duration: 0.5 }, 0.8)
      .from('.badge', { opacity: 0, rotation: -60, transformOrigin: '50% 50%', duration: 0.9, ease: 'expo.out' }, 0.45);

    /* 3. 半島マークがスクロールで少し沈む（登場は scaleX、沈みは yPercent と別のプロパティ・別の要素） */
    gsap.to('.hero-mark', { yPercent: 10, ease: 'none', scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true } });
    /* バッジはページ全体のスクロールで 1 回転（登場の rotation は中の svg、回転は外の枡と分ける） */
    gsap.to('.badge-spin', { rotation: 360, ease: 'none', scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: 0.4 } });

    /* 4. 節の見出しが行ごとに下から現れ、英字の一言が続く（1 回だけ） */
    gsap.utils.toArray('main .section h2').forEach(function (h) {
      var lines = h.querySelectorAll('.nb');
      var head = h.closest('.sec-head') || h.parentElement;
      var one = head.querySelector('.one');
      var eyebrow = head.querySelector('.eyebrow');
      var t = gsap.timeline({ scrollTrigger: { trigger: h, start: 'top 86%', once: true } });
      if (eyebrow) t.from(eyebrow, { opacity: 0, x: -12, duration: 0.5, ease: ease }, 0);
      t.from(lines, { yPercent: 115, duration: 0.9, ease: 'power4.out', stagger: 0.1 }, 0.05);
      if (one) t.from(one, { opacity: 0, y: 14, duration: 0.6, ease: ease }, 0.35);
    });
    /* フッターの合言葉も同じ出方 */
    var ftag = document.querySelector('.footer .tag');
    if (ftag) gsap.from(ftag.querySelectorAll('.nb'), { yPercent: 115, duration: 0.9, ease: 'power4.out', stagger: 0.1, scrollTrigger: { trigger: ftag, start: 'top 92%', once: true } });

    /* 4. 見せたい塊だけ順に（番号の段・セッション・コース・表の行・概要の行・目指すもの） */
    ScrollTrigger.batch('.reveal, .sched .row, .aims .row, .spec > div', {
      start: 'top 90%', once: true,
      onEnter: function (els) { gsap.from(els, { opacity: 0, y: 18, duration: 0.6, ease: ease, stagger: 0.07, overwrite: 'auto' }); }
    });
    /* 番号は少し大きい状態から収まる */
    gsap.utils.toArray('.numbered .no, .fields .en').forEach(function (el) {
      gsap.from(el, { scale: 1.3, transformOrigin: '0 0', duration: 0.8, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 90%', once: true } });
    });
    /* DAY の大きな英字は左から滑り込む（スクロールに合わせて） */
    gsap.utils.toArray('.day .day-head .en').forEach(function (el) {
      gsap.from(el, { x: -40, opacity: 0, ease: 'none', scrollTrigger: { trigger: el, start: 'top 95%', end: 'top 60%', scrub: true } });
    });

    /* 2. 数字のカウントアップ（最後は必ず元の表記） */
    gsap.utils.toArray('.count').forEach(function (el) {
      var to = parseInt(el.getAttribute('data-to'), 10);
      var final = el.textContent;
      var obj = { v: 0 };
      gsap.to(obj, {
        v: to, duration: 1.1, ease: 'expo.out',
        scrollTrigger: { trigger: el, start: 'top 88%', once: true },
        onUpdate: function () { el.textContent = Math.round(obj.v).toLocaleString('ja-JP'); },
        onComplete: function () { el.textContent = final; }
      });
    });

    /* 5. 写真が幕のように開く（左から）。横長の 1 枚はスクロールで枠いっぱいに広がる（React Bits「Scroll Expand」の考え方） */
    gsap.utils.toArray('.curtain').forEach(function (el) {
      gsap.from(el, { clipPath: 'inset(0 100% 0 0)', duration: 0.9, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 85%', once: true } });
      var img = el.querySelector('img');
      if (img) gsap.from(img, { scale: 1.06, duration: 1.4, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 85%', once: true } });
    });
    gsap.utils.toArray('.photo.wide').forEach(function (el) {
      gsap.fromTo(el, { scale: 0.9, borderRadius: 16 }, { scale: 1, borderRadius: 0, ease: 'none', scrollTrigger: { trigger: el, start: 'top 85%', end: 'top 30%', scrub: 0.5 } });
    });

    /* 6-1. 町の名前の帯: 基本は 48 秒で 1 周。スクロールが速いほど速く流れ、止まると 1 倍に戻る */
    var track = document.querySelector('.marquee-track');
    if (track) {
      var loop = gsap.to(track, { xPercent: -50, duration: 48, ease: 'none', repeat: -1 });
      var target = 1;
      ScrollTrigger.create({ onUpdate: function (self) { target = 1 + Math.min(Math.abs(self.getVelocity()) / 350, 5); } });
      gsap.ticker.add(function () {
        loop.timeScale(gsap.utils.interpolate(loop.timeScale(), target, 0.08));
        target += (1 - target) * 0.04;
      });
    }

    /* 6-2. 日付のパタパタ板: 見えたら各マスが数字を回して止まる（右のマスほど長く回る） */
    var flap = document.querySelector('.flap');
    if (flap) {
      var cells = flap.querySelectorAll('.cell[data-ch]');
      ScrollTrigger.create({
        trigger: flap, start: 'top 85%', once: true,
        onEnter: function () {
          cells.forEach(function (cell, i) {
            var final = cell.getAttribute('data-ch');
            var steps = 8 + i * 3, n = 0;
            var iv = setInterval(function () {
              n++;
              if (n >= steps) { cell.textContent = final; clearInterval(iv); gsap.fromTo(cell, { scaleY: 0.6 }, { scaleY: 1, duration: 0.25, ease: 'power2.out' }); return; }
              cell.textContent = String((parseInt(final, 10) + n) % 10);
            }, 55);
          });
        }
      });
    }

    /* ページ内リンクは最後ゆっくり止まる（固定ヘッダーの高さぶん手前で） */
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var id = a.getAttribute('href');
        var target = id.length > 1 && document.querySelector(id);
        if (!target) return;
        e.preventDefault();
        gsap.to(window, { duration: 0.9, ease: 'power3.inOut', scrollTo: { y: target, offsetY: 64 } });
      });
    });

    /* 画像の読み込み後に位置を測り直す */
    window.addEventListener('load', function () { ScrollTrigger.refresh(); });
  });

  /* 7. PC だけ: ボタンが指先に少し寄る。スマホ・LINE では枠ごと動かない */
  mm.add('(prefers-reduced-motion: no-preference) and (hover: hover) and (pointer: fine)', function () {
    document.querySelectorAll('.btn-primary').forEach(function (btn) {
      var xTo = gsap.quickTo(btn, 'x', { duration: 0.3, ease: 'power2.out' });
      var yTo = gsap.quickTo(btn, 'y', { duration: 0.3, ease: 'power2.out' });
      btn.addEventListener('mousemove', function (e) {
        var r = btn.getBoundingClientRect();
        xTo(((e.clientX - r.left) / r.width - 0.5) * 12);
        yTo(((e.clientY - r.top) / r.height - 0.5) * 8);
      });
      btn.addEventListener('mouseleave', function () { xTo(0); yTo(0); });
    });
  });
})();
