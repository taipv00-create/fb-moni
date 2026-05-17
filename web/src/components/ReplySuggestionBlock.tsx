'use client';

import type { ReplySuggestion } from '@/lib/types';
import { pct } from '@/lib/format';

async function copyText(text: string, btn: HTMLButtonElement) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  const prev = btn.textContent;
  btn.textContent = 'Đã copy';
  setTimeout(() => {
    btn.textContent = prev;
  }, 1600);
}

export function ReplySuggestionBlock({ item }: { item: ReplySuggestion }) {
  const conf = pct(item.confidence);
  const source =
    item.target_source === 'comment'
      ? 'Bình luận'
      : item.target_source === 'manual_comment'
        ? 'Comment nhập tay'
        : 'Bài viết';

  return (
    <div className="reply-wrap">
      <div className="reply-head">
        <span>🤖 Gợi ý trả lời cho sale</span>
        <span>
          {item.intent_label || 'khác'}
          {conf ? ` · ${conf}` : ''}
        </span>
      </div>
      <div className="reply-meta">
        <div>
          <b>Nguồn:</b> {source}
          {item.customer_name ? ` · ${item.customer_name}` : ''}
        </div>
        <div>
          <b>Ý khách:</b> {item.customer_need || 'AI chưa xác định rõ'}
        </div>
        {item.recommended_approach ? (
          <div>
            <b>Hướng xử lý:</b> {item.recommended_approach}
          </div>
        ) : null}
        {item.business_phone ? (
          <div>
            <b>SĐT bên mình:</b>{' '}
            <span className="lead-phone">{item.business_phone}</span>
          </div>
        ) : null}
        {item.storage ? (
          <div className="reply-save-note">Đã lưu: {item.storage === 'supabase' ? 'Supabase' : 'local'}</div>
        ) : null}
        {item.warning ? <div className="reply-save-note">⚠️ {item.warning}</div> : null}
      </div>
      <div className="reply-list">
        {(item.suggested_replies || []).map((reply, i) => (
          <div key={i} className="reply-item">
            <div className="reply-label">{reply.label || 'Mẫu trả lời'}</div>
            <div className="reply-text">{reply.text || ''}</div>
            <div className="reply-actions">
              <button
                type="button"
                className="btn-copy-reply"
                onClick={(e) => void copyText(reply.text || '', e.currentTarget)}
              >
                Copy
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
