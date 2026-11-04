// Slack に投げる文面（Functions 本体から切り離して、ローカルでテストできるようにしてある）
const PLAN_LABEL = { space: 'スペースのみ', light: '軽食', party: 'パーティー' };
const ADMIN_URL = 'https://bokashi-rental.web.app';

function fmtDate(s) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s || '')) return s || '未定';
  const d = new Date(s + 'T00:00:00+09:00');
  const dow = ['日', '月', '火', '水', '木', '金', '土'][d.getDay()];
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}（${dow}）`;
}
const yen = (n) => '¥' + Math.round(Number(n) || 0).toLocaleString('ja-JP');

const PAY_LABEL = { onsite: '当日の現地払い（現金・カード）', invoice: '請求書払い（振込）' };
function payText(b) {
  if (!b.payment) return '未指定';
  const base = PAY_LABEL[b.payment] || String(b.payment);
  if (b.payment !== 'invoice') return base;
  return `${base}　宛名：${b.invoiceTo || '—'}／但し書き：${b.invoiceNote || 'レンタルスペース利用料として'}`;
}

/** 予約ドキュメント（rentalBookings の1件）から Slack 用の本文を作る */
function buildSlackMessage(b) {
  const who = [b.org, b.name ? `${b.name} 様` : ''].filter(Boolean).join(' ') || '（名前なし）';
  const plan = `${PLAN_LABEL[b.plan] || 'スペースのみ'}${b.drink ? '＋飲み放題' : ''}${b.trash ? '＋ゴミ回収' : ''}`;
  const lines = [
    `:new: *レンタルスペースの申込が入りました*　受付番号 \`${b.receipt || b.id || '-'}\``,
    `第1希望：${fmtDate(b.date)} ${b.start || ''}〜${b.end || ''} ／ ${b.people || '?'}名 ／ ${b.kind || '用途未記入'}`,
    b.date2 ? `第2希望：${fmtDate(b.date2)}` : null,
    `内容：${b.purpose || '（未記入）'}`,
    `${who}${b.email ? `（${b.email}${b.phone ? ' / ' + b.phone : ''}）` : ''}`,
    `プラン：${plan}　お見積：${yen(b.estimate)}〜`,
    `支払い：${payText(b)}`,
    b.note ? `ご要望：${b.note}` : null,
    `→ 管理画面で確認: ${ADMIN_URL}`,
  ].filter(Boolean);
  return { text: lines.join('\n'), unfurl_links: false };
}

/** Incoming Webhook に投稿する。成功で true、失敗は例外 */
async function postToSlack(webhookUrl, payload, fetchImpl = fetch) {
  const res = await fetchImpl(webhookUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(`Slack webhook ${res.status}: ${await res.text()}`);
  return true;
}

module.exports = { buildSlackMessage, postToSlack, fmtDate };
