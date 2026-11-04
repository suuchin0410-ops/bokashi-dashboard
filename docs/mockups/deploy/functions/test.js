// ローカルテスト: 本文の組み立てと、Webhook への POST（ローカルの受け口で中身を確かめる）。本番には触れない
const assert = require('node:assert/strict');
const http = require('node:http');
const { buildSlackMessage, postToSlack, fmtDate } = require('./message');

const sample = { id: 'RQ-261104-9KYY', receipt: 'RQ-261104-9KYY', source: 'web', status: 'draft', date: '2026-11-14', date2: '', start: '13:00', end: '16:00', people: 12, kind: '会議・研修', purpose: '本番の動作確認', plan: 'space', drink: false, trash: false, name: 'テスト 太郎', org: '動作確認', email: 'test@example.com', phone: '011-000-0000', note: '', tour: false, estimate: 46200 };

assert.equal(fmtDate('2026-11-14'), '2026/11/14（土）');
const msg = buildSlackMessage(sample);
assert.match(msg.text, /受付番号 `RQ-261104-9KYY`/);
assert.match(msg.text, /2026\/11\/14（土） 13:00〜16:00 ／ 12名 ／ 会議・研修/);
assert.match(msg.text, /動作確認 テスト 太郎 様（test@example.com \/ 011-000-0000）/);
assert.match(msg.text, /¥46,200〜/);
assert.match(msg.text, /https:\/\/bokashi-rental\.web\.app/);
assert.doesNotMatch(msg.text, /第2希望/);
const msg2 = buildSlackMessage({ ...sample, date2: '2026-11-21', drink: true, plan: 'party', note: 'ベジタリアン2名' });
assert.match(msg2.text, /第2希望：2026\/11\/21（土）/);
assert.match(msg2.text, /パーティー＋飲み放題/);
assert.match(msg2.text, /ご要望：ベジタリアン2名/);
assert.match(msg.text, /支払い：未指定/);
const msg3 = buildSlackMessage({ id: 'RQ-261104-TEST', payment: 'invoice', invoiceTo: '株式会社テスト', invoiceNote: '会場利用料として' });
assert.match(msg3.text, /支払い：請求書払い（振込）　宛名：株式会社テスト／但し書き：会場利用料として/);
const msg4 = buildSlackMessage({ id: 'RQ-261104-TEST', payment: 'onsite' });
assert.match(msg4.text, /支払い：当日の現地払い（現金・カード）/);
console.log('message OK');
console.log('--- 本文プレビュー ---\n' + msg.text + '\n---');

// Webhook の受け口を立てて POST を確かめる
const received = [];
const server = http.createServer((req, res) => { let body = ''; req.on('data', c => body += c); req.on('end', () => { received.push({ ct: req.headers['content-type'], body: JSON.parse(body) }); res.writeHead(200); res.end('ok'); }); });
server.listen(0, '127.0.0.1', async () => {
  const url = `http://127.0.0.1:${server.address().port}/hook`;
  try {
    assert.equal(await postToSlack(url, msg), true);
    assert.equal(received.length, 1);
    assert.equal(received[0].ct, 'application/json');
    assert.equal(received[0].body.text, msg.text);
    // 失敗（4xx）は例外
    await assert.rejects(postToSlack(url, msg, async () => ({ ok: false, status: 403, text: async () => 'invalid_token' })), /403/);
    console.log('post OK');
  } finally { server.close(); }
});
