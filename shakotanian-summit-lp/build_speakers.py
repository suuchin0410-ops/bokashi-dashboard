# speakers/speakers.json → speakers/index.html と speakers/<slug>.html
# 見た目は assets/site.css（LP と共通）+ assets/speakers.css。動きは js/motion.js + js/speakers.js
# 2026-11-13 鈴木さん「登壇者ページもタイポグラフィと動きの演出で」→ design/28_TYPO_PHOTO_LP.md の型（表紙は暗い面に大きな名前、読む段は明るい面）
import json, html, pathlib
root = pathlib.Path(__file__).parent
data = json.loads((root/'speakers'/'speakers.json').read_text(encoding='utf-8'))
SESS = {s['no']: s for s in data['sessions']}
SP = data['speakers']
FORM = 'https://forms.gle/kHrXC5uL7YQUNuEFA'
esc = html.escape

def mark(cls='mark'):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#hanto"/></svg>'

SYMBOL = '''<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="hanto" viewBox="0 0 24 24">
    <path d="M12 2a10 10 0 0 0 0 20z" fill="currentColor"/>
    <path d="M12 2a10 10 0 0 1 0 20" fill="none" stroke="currentColor" stroke-width="1.8"/>
  </symbol>
</svg>'''

def page(title, desc, body, canonical, body_cls=''):
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<!-- 登壇者ページ。build_speakers.py が speakers/speakers.json から作る（手で直さない）。決まりは ../index.html 冒頭と design/02_BRANDS.md -->
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="article">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%230E6FA6'/%3E%3Cpath d='M32 14a18 18 0 0 0 0 36z' fill='%23fff'/%3E%3Cpath d='M32 14a18 18 0 0 1 0 36' fill='none' stroke='%23fff' stroke-width='3'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@700&family=Zen+Kaku+Gothic+New:wght@400;700&family=Zalando+Sans:wdth,wght@75,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../assets/site.css">
<link rel="stylesheet" href="../assets/speakers.css">
</head>
<body class="{body_cls}">
{SYMBOL}
<div class="progress" aria-hidden="true"></div>
<header class="header dark">
  <div class="wrap">
    <a class="wordmark" href="../index.html" aria-label="シャコタニアンサミット 3 in 余市 のトップへ">{mark()}SHAKOTANIAN SUMMIT 3</a>
    <nav class="nav" aria-label="ページ"><a href="../iwanai.html" target="_blank" rel="noopener">前回の様子</a><a href="index.html" aria-current="page">登壇者紹介</a></nav>
    <a class="btn btn-primary" href="{FORM}" target="_blank" rel="noopener" data-cta-type="apply" data-cta-section="header">申し込む</a>
  </div>
</header>
<main id="top">
{body}
</main>
<footer class="footer">
  <div class="wrap">
    <div>
      <a class="wordmark" href="../index.html">{mark()}SHAKOTANIAN SUMMIT 3 / YOICHI</a>
      <p class="tag"><span class="nb">やべえ<span class="h">半</span>島を、</span><span class="nb">つくる。</span></p>
      <p class="one">Half island. <span class="hi">Whole life.</span></p>
    </div>
    <div class="meta">
      <span>シャコタニアンサミット in 余市実行委員会</span>
      <span>2026.11.21 SAT – 11.22 SUN</span>
      <a href="index.html">登壇者一覧</a>
      <a href="../iwanai.html" target="_blank" rel="noopener">前回の様子</a>
      <a href="../index.html#program">2 日間の流れ</a>
    </div>
  </div>
</footer>
<script src="../js/gsap.min.js" defer></script>
<script src="../js/ScrollTrigger.min.js" defer></script>
<script src="../js/ScrollToPlugin.min.js" defer></script>
<script src="../js/motion.js" defer></script>
<script src="../js/speakers.js" defer></script>
</body>
</html>
'''

BIG_MARK = '''<svg class="big" viewBox="0 0 24 24" aria-hidden="true"><path class="fill" d="M12 2a10 10 0 0 0 0 20z" fill="currentColor"/><path class="line" d="M12 2a10 10 0 0 1 0 20" fill="none" stroke="currentColor" stroke-width=".5" pathLength="100"/></svg>'''

def paras(lst, cls=''):
    c = f' class="{cls}"' if cls else ''
    return '\n'.join(f'<p{c}>{p}</p>' for p in lst)  # 本文は信頼できる自前の文なので HTML を許す（<a> など）

def profile(i, s):
    sess = SESS[s['session']]
    prev = SP[i-1] if i > 0 else None
    nxt = SP[i+1] if i+1 < len(SP) else None
    links = ''.join(f'<li>{mark()}<span><a href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])}</a>{("<span class=sub>"+esc(l["note"])+"</span>") if l.get("note") else ""}</span></li>' for l in s.get('links', []))
    srcs = ''.join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(u)}</a></li>' for u in s.get('sources', []))
    quote = ''
    if s.get('quote'):
        q = s['quote']
        quote = f'''<section class="section dark sp-quote-sec" aria-label="本人の言葉">
    <div class="wrap">
      <p class="kicker">{mark()}In their words</p>
      <p class="sp-quote">{q["text"]}</p>
      <p class="sp-quote-src">{esc(q.get("src",""))}{(' <a href="'+esc(q["url"])+'" target="_blank" rel="noopener">出典</a>') if q.get("url") else ""}</p>
    </div>
  </section>'''
    pending = f'<p class="pending">{esc(s["pending"])}</p>' if s.get('pending') else ''
    nav = ''
    if prev: nav += f'<a class="prev" href="{prev["slug"]}.html">{mark()}<span><span class="lbl">Prev</span><br><span class="nm">{esc(prev["name"])}</span></span></a>'
    else: nav += f'<a class="prev" href="index.html">{mark()}<span><span class="lbl">List</span><br><span class="nm">登壇者一覧</span></span></a>'
    if nxt: nav += f'<a class="next" href="{nxt["slug"]}.html"><span><span class="lbl">Next</span><br><span class="nm">{esc(nxt["name"])}</span></span>{mark()}</a>'
    else: nav += f'<a class="next" href="index.html"><span><span class="lbl">List</span><br><span class="nm">登壇者一覧</span></span>{mark()}</a>'
    body = f'''  <section class="hero dark sp-cover" aria-labelledby="h-title">
    {BIG_MARK}
    <div class="wrap">
      <div class="hero-in">
        <a class="sp-session" href="../index.html#sessions">{mark()}Session {sess["no"]}<span class="ja">{esc(sess["title"])}</span></a>
        {('<p class="kana">'+esc(s.get("kana",""))+((" / "+esc(s["en"])) if s.get("en") else "")+'</p>') if (s.get("kana") or s.get("en")) else ""}
        <h1 id="h-title"><span class="nb">{esc(s["name"])}</span></h1>
        <p class="role">{esc(s["org"])}{("<small>"+esc(s["title"])+"</small>") if s.get("title") else ""}</p>
        <p class="lead">{s["summary"]}</p>
      </div>
    </div>
  </section>
  {quote}
  <section class="section" aria-label="紹介">
    <div class="wrap sp-body">
      <div>
        <span class="en">Now</span>
        <h2><span class="nb">いま、していること</span></h2>
        {paras(s.get("now", []))}
      </div>
      <div>
        <span class="en">Past</span>
        <h2><span class="nb">これまで</span></h2>
        {paras(s.get("past", []))}
      </div>
      <div>
        <span class="en">On stage</span>
        <h2><span class="nb">サミットで話すこと</span></h2>
        <p class="q">{esc(sess["q"])}</p>
        <p class="sub">SESSION {sess["no"]}「{esc(sess["title"])}」{esc(sess["theme"])}　11 月 21 日（土）14:00–17:00・かくと徳島屋</p>
      </div>
      {("<div><span class=en>Links</span><h2><span class=nb>リンク</span></h2><ul class=links>"+links+"</ul></div>") if links else ""}
      {pending}
    </div>
  </section>
  <section class="section section-alt" aria-label="ほかの登壇者">
    <div class="wrap">
      <nav class="sp-nav" aria-label="前後の登壇者">{nav}</nav>
      {("<div class=sources style='margin-top:var(--s-10)'>この紹介文は次の公開情報からまとめました（"+esc(data["checked"])+" 確認）<ol>"+srcs+"</ol></div>") if srcs else ""}
    </div>
  </section>'''
    return page(f'{s["name"]}（{s["org"]}）｜登壇者｜シャコタニアンサミット 3 in 余市', s['desc'], body, f'speakers/{s["slug"]}.html')

def index():
    groups = ''
    for no, sess in SESS.items():
        items = ''.join(f'<li><a href="{s["slug"]}.html"><span class="nm">{esc(s["name"])}{("<small>"+esc(s["kana"])+"</small>") if s.get("kana") else ""}</span><span class="org">{esc(s["org"])}{("　"+esc(s["title"])) if s.get("title") else ""}</span><span class="sum">{s["summary"]}</span>{mark()}</a></li>' for s in SP if s['session']==no)
        groups += f'''      <div class="sp-group" id="session{no}">
        <span class="en">Session {no}</span>
        <h2><span class="nb">{esc(sess["title"])}</span></h2>
        <p class="theme">{esc(sess["theme"])}</p>
        <p class="q">{esc(sess["q"])}</p>
        <ul class="sp-list">{items}</ul>
      </div>
'''
    body = f'''  <section class="hero dark" aria-labelledby="h-title">
    <div class="hero-bg" aria-hidden="true"><img src="../assets/img/iwanai-talk2.webp" alt="" width="1600" height="1200" fetchpriority="high" decoding="async"></div>
    <div class="wrap">
      <div class="hero-in">
        <p class="one">Eight voices, <span class="hi">one peninsula.</span></p>
        <h1 id="h-title"><span class="nb">登壇する、</span><span class="nb"><span class="h">8</span> 人。</span></h1>
        <p class="lead">11 月 21 日（土）14:00 からの 3 つのセッション。土地、人と共同、未来と進化の順に、視点を広げていきます。名前を押すと紹介ページが開きます。</p>
      </div>
    </div>
    <p class="credit">写真: 第 2 回 in 岩内（2025 年 11 月）のトークセッション</p>
  </section>
  <section class="section" aria-label="登壇者一覧" id="sessions">
    <div class="wrap">
{groups}    </div>
  </section>
  <section class="section dark photo-scene sp-cta" aria-labelledby="h-cta">
    <div class="scene-bg" aria-hidden="true"><img src="../assets/img/iwanai-dusk.webp" alt="" width="1600" height="1200" loading="lazy" decoding="async"></div>
    <div class="wrap">
      <div class="sec-head">
        <h2 id="h-cta"><span class="nb">会いに、</span><span class="nb">来てください。</span></h2>
        <p class="one">Yoichi, <span class="hi">Nov. 21–22.</span></p>
      </div>
      <div class="btn-row"><a class="btn btn-primary" href="{FORM}" target="_blank" rel="noopener" data-cta-type="apply" data-cta-section="speakers">{mark()}参加を申し込む</a><a class="btn btn-ghost" href="../index.html#program">2 日間の流れを見る</a></div>
      <p class="btn-note">申込フォーム（Google フォーム）が別のタブで開きます。</p>
    </div>
    <p class="credit">写真: 第 2 回 in 岩内、夕暮れの会場前</p>
  </section>'''
    return page('登壇者｜シャコタニアンサミット 3 in 余市', '2026年11月21日のセッション 1〜3 に登壇する 8 人の紹介。土地・人・未来の 3 つの問いを、積丹半島で生きる人と考えます。', body, 'speakers/index.html', 'sp-index')

out = root/'speakers'
(out/'index.html').write_text(index(), encoding='utf-8')
for i, s in enumerate(SP):
    (out/f'{s["slug"]}.html').write_text(profile(i, s), encoding='utf-8')
print('built', len(SP)+1, 'pages')
