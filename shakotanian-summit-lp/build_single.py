# index.html → dist/shakotanian-summit-3.html（Claude の Artifact ではない、そのまま開ける 1 ファイルの HTML）
# 画像は base64 で中に入れる。GSAP は js/ の 3 本を中に入れる（ネット無しでも動く）。書体だけ Google Fonts（無ければ端末の明朝・ゴシックで出る）
import re, base64, pathlib
root = pathlib.Path(__file__).parent
src = (root/'index.html').read_text(encoding='utf-8')
def img(m):
    path = root/m.group(1)
    b = base64.b64encode(path.read_bytes()).decode()
    return f'src="data:image/webp;base64,{b}"'
out = re.sub(r'src="(assets/img/[^"]+\.webp)"', img, src)
out = out.replace('href="speakers/', 'href="https://shakotanian-summit-3.vercel.app/speakers/')
out = out.replace('href="iwanai.html"', 'href="https://shakotanian-summit-3.vercel.app/iwanai.html"')  # 特設ページも Vercel 側  # 登壇者ページは Vercel 側
out = out.replace('<link rel="stylesheet" href="assets/site.css">', '<style>\n' + (root/'assets'/'site.css').read_text(encoding='utf-8') + '</style>')
scripts = ''
for n in ('gsap','ScrollTrigger','ScrollToPlugin','motion'):
    scripts += f'<script>\n{(root/"js"/(n+".min.js" if n!="motion" else "motion.js")).read_text(encoding="utf-8")}\n</script>\n'
out = re.sub(r'(<script src="js/[^"]+" defer></script>\n?)+', lambda m: scripts, out)
out = out.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
(root/'dist').mkdir(exist_ok=True)
dst = root/'dist'/'shakotanian-summit-3.html'
dst.write_text(out, encoding='utf-8')
print(dst, len(out)//1024, 'KB')
