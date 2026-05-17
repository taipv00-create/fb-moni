'use client';

import type { CommentSummary } from '@/lib/types';

export function CommentSummaryBlock({ item }: { item: CommentSummary }) {
  return (
    <div className="reply-wrap comment-summary-wrap">
      <div className="reply-head">
        <span>📊 AI tóm tắt bình luận</span>
        <span>
          {item.comment_count ?? 0} comment
          {item.fetched_comment_count !== undefined ? ` · đã đọc ${item.fetched_comment_count}` : ''}
        </span>
      </div>
      <div className="reply-meta">
        <div>
          <b>Tóm tắt:</b> {item.summary || 'Chưa có tóm tắt'}
        </div>
        <div>
          <b>Sắc thái:</b> {item.sentiment || 'unknown'} · <b>Mức gấp:</b> {item.urgency || 'low'} ·{' '}
          <b>Người tham gia:</b> {item.comment_authors_count ?? 0}
        </div>
        {item.main_topics?.length ? (
          <div>
            <b>Chủ đề:</b> {item.main_topics.join(', ')}
          </div>
        ) : null}
        {item.recommended_action ? (
          <div>
            <b>Việc nên làm:</b> {item.recommended_action}
          </div>
        ) : null}
        {item.storage ? (
          <div className="reply-save-note">Đã lưu: {item.storage === 'supabase' ? 'Supabase' : 'local'}</div>
        ) : null}
        {item.warning ? <div className="reply-save-note">⚠️ {item.warning}</div> : null}
      </div>
      {item.customer_intents?.length ? (
        <div className="summary-list">
          <div className="reply-label">Ý định khách hàng</div>
          {item.customer_intents.slice(0, 6).map((intent, i) => (
            <div key={i} className="summary-line">
              <b>{intent.intent || 'khác'}</b>
              {intent.count !== undefined ? ` (${intent.count})` : ''}: {intent.evidence || ''}
            </div>
          ))}
        </div>
      ) : null}
      {item.top_questions?.length ? (
        <div className="summary-list">
          <div className="reply-label">Câu hỏi nổi bật</div>
          {item.top_questions.slice(0, 5).map((question, i) => (
            <div key={i} className="summary-line">
              {question}
            </div>
          ))}
        </div>
      ) : null}
      {item.lead_signals?.length ? (
        <div className="summary-list">
          <div className="reply-label">Dấu hiệu lead</div>
          {item.lead_signals.slice(0, 5).map((lead, i) => (
            <div key={i} className="summary-line">
              <b>{lead.author || 'Khách'}</b>: {lead.need || lead.evidence || ''}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
