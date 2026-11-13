# index.html → artifact.html（Artifact の決まり: doctype/html/head/body 無し・title と meta と style を先頭・GSAP は cdnjs・motion.js は中に入れる）
import re, pathlib
src = pathlib.Path(__file__).with_name('index.html').read_text(encoding='utf-8')
head = src[src.index('<head>')+6:src.index('</head>')]
body = src[src.index('<body>')+6:src.index('</body>')]
keep = []
for m in re.finditer(r'<title>.*?</title>|<meta name="claude:viewport-fit-sides"[^>]*>|<meta name="description"[^>]*>|<meta property="og:[^>]*>|<link rel="icon"[^>]*>|<link rel="preconnect"[^>]*>|<link href="https://fonts.googleapis.com[^>]*>|<link rel="stylesheet" href="assets/site.css">', head, re.S):
    g = m.group(0)
    if 'site.css' in g: g = '<style>\n' + pathlib.Path(__file__).with_name('assets').joinpath('site.css').read_text(encoding='utf-8') + '</style>'
    keep.append(g)
body = re.sub(r'\n<script src="js/[^"]+" defer></script>', '', body)
motion = pathlib.Path(__file__).with_name('js').joinpath('motion.js').read_text(encoding='utf-8')
scripts = ''.join(f'<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.15.0/{n}.min.js"></script>\n' for n in ('gsap','ScrollTrigger','ScrollToPlugin'))
out = '\n'.join(keep) + '\n' + body.rstrip() + '\n' + scripts + '<script>\n' + motion + '\n</script>\n'
out = out.replace('href="speakers/', 'href="https://shakotanian-summit-3.vercel.app/speakers/')
out = out.replace('href="iwanai.html"', 'href="https://shakotanian-summit-3.vercel.app/iwanai.html"')  # 特設ページも Vercel 側  # 登壇者ページは Vercel 側
pathlib.Path(__file__).with_name('artifact.html').write_text(out, encoding='utf-8')
print('artifact.html', len(out))
