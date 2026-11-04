/**
 * bokashi Base レンタルスペース予約（bokashi-rental.web.app）の Cloud Functions。
 * codebase "rental" として bokashi-ops-app にデプロイする（OPSアプリの Functions とは別。es-ops-app には置かない）。
 *   デプロイ: cd docs/mockups/deploy && firebase deploy --only functions:rental --project bokashi-ops-app
 *   Webhook:  firebase functions:secrets:set SLACK_WEBHOOK_RENTAL --project bokashi-ops-app（Slack の Incoming Webhook URL を貼る）
 */
const { setGlobalOptions } = require('firebase-functions/v2');
const { onDocumentCreated } = require('firebase-functions/v2/firestore');
const { defineSecret } = require('firebase-functions/params');
const { logger } = require('firebase-functions');
const { initializeApp } = require('firebase-admin/app');
const { getFirestore, FieldValue } = require('firebase-admin/firestore');
const { buildSlackMessage, postToSlack } = require('./message');

setGlobalOptions({ region: 'asia-northeast1', maxInstances: 5 });
initializeApp();

const SLACK_WEBHOOK_RENTAL = defineSecret('SLACK_WEBHOOK_RENTAL');

/**
 * Web 申込（お客様用フォーム）が rentalBookings に作られたら Slack に通知する。
 * スタッフが「予約を登録」で入れた分（source: staff）は通知しない。
 * 同じ文書に二度通知しないよう、送ったら slackNotifiedAt を記録する。
 */
exports.notifyRentalRequest = onDocumentCreated(
  { document: 'stores/store_bokashi/rentalBookings/{bookingId}', secrets: [SLACK_WEBHOOK_RENTAL] },
  async (event) => {
    const snap = event.data;
    if (!snap) return;
    const b = snap.data() || {};
    if (b.source !== 'web') { logger.info('skip (not web)', { id: snap.id, source: b.source }); return; }
    if (b.slackNotifiedAt) { logger.info('skip (already notified)', { id: snap.id }); return; }
    const url = SLACK_WEBHOOK_RENTAL.value();
    if (!url) { logger.error('SLACK_WEBHOOK_RENTAL が未設定です'); return; }
    try {
      await postToSlack(url, buildSlackMessage({ id: snap.id, ...b }));
      await getFirestore().doc(snap.ref.path).set({ slackNotifiedAt: FieldValue.serverTimestamp() }, { merge: true });
      logger.info('Slack に通知しました', { id: snap.id });
    } catch (e) {
      // 失敗しても申込自体は保存されている。ログに残して終わる（再試行で二重投稿しないため）
      logger.error('Slack 通知に失敗', { id: snap.id, error: String(e && e.message || e) });
    }
  }
);
