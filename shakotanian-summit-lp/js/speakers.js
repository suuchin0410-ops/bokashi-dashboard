/* 登壇者ページの動き（motion.js のあとに読む・GSAP 3.15.0）
   決まり: 21_GSAP.md（power3/expo・弾まない・減らす設定で止まる）・12_REACT_BITS.md「Blur Text」を素の JS で・28_TYPO_PHOTO_LP.md
   1 読み進みの線  2 表紙の半島マークが線で描かれて塗られる（motion.js の表紙の登場と同時）
   3 本人の言葉が 1 文字ずつピントが合う  4 一覧の名前が左からすっと出る
   表紙の名前（h1）の 1 文字ずつは motion.js の表紙の登場がそのまま効く（.hero h1） */
(function () {
  if (!window.gsap || !window.ScrollTrigger) return;
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
        else if (n.nodeType === 1 && n.classList.contains('h')) { n.classList.add('ch'); out.push(n); }
        else if (n.nodeType === 1) { walk(n, n); }
      });
    })(el, el);
    return out;
  }

  mm.add('(prefers-reduced-motion: no-preference)', function () {
    /* 1. 読み進みの線 */
    var bar = document.querySelector('.progress');
    if (bar) gsap.to(bar, { scaleX: 1, ease: 'none', scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: 0.3 } });

    /* 2. 表紙の半島マーク: 線が描かれ、塗りが右から満ちる */
    var big = document.querySelector('.sp-cover .big');
    if (big) {
      gsap.from(big.querySelector('.fill'), { scaleX: 0, duration: 1.2, ease: 'expo.out', delay: 0.1 });
      gsap.from(big.querySelector('.line'), { strokeDashoffset: 100, duration: 1.3, ease: 'power2.inOut', delay: 0.1 });
      gsap.to(big, { yPercent: 12, ease: 'none', scrollTrigger: { trigger: '.sp-cover', start: 'top top', end: 'bottom top', scrub: true } });
    }

    /* 3. 本人の言葉: 1 文字ずつぼやけからピントが合う（見えたら 1 回） */
    document.querySelectorAll('.sp-quote').forEach(function (q) {
      var chars = splitChars(q);
      gsap.from(chars, { opacity: 0, y: 24, filter: 'blur(10px)', duration: 0.7, ease: 'power4.out', stagger: 0.02, scrollTrigger: { trigger: q, start: 'top 82%', once: true } });
    });

    /* 4. 一覧の名前: 左から 24px すっと（行ごと・1 回） */
    gsap.utils.toArray('.sp-list .nm').forEach(function (nm) {
      gsap.from(nm, { x: -24, opacity: 0, duration: 0.8, ease: 'power3.out', scrollTrigger: { trigger: nm, start: 'top 90%', once: true } });
    });
    /* セッションの大きな英字は少し大きい状態から収まる */
    gsap.utils.toArray('.sp-body .en').forEach(function (el) {
      gsap.from(el, { scale: 1.2, transformOrigin: '0 0', opacity: 0, duration: 0.8, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 90%', once: true } });
    });
  });
})();
