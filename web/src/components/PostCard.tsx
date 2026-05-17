'use client';

import React, { useState } from 'react';
import { api } from '@/lib/api';
import { catBg, catFg } from '@/lib/constants';
import { LeadBlock } from '@/components/LeadBlock';
import { CommentSummaryBlock } from '@/components/CommentSummaryBlock';
import { ReplySuggestionBlock } from '@/components/ReplySuggestionBlock';
import type { CommentSummary, FbPage, FbPost, Lead, ReplySuggestion } from '@/lib/types';
import { avatarColor, escRegex, initials, timeAgo } from '@/lib/utils';

function HighlightText({ text, keywords }: { text: string; keywords: string[] }) {
  if (!keywords.length) return <>{text}</>;
  let nodes: React.ReactNode[] = [text];
  keywords.forEach((kw, kwi) => {
    if (!kw.trim()) return;
    const next: React.ReactNode[] = [];
    const re = new RegExp(`(${escRegex(kw)})`, 'gi');
    nodes.forEach((node, ni) => {
      if (typeof node !== 'string') {
        next.push(node);
        return;
      }
      node.split(re).forEach((part, pi) => {
        if (!part) return;
        if (pi % 2 === 1) {
          next.push(
            <span key={`h-${kwi}-${ni}-${pi}`} className="hl">
              {part}
            </span>,
          );
        } else {
          next.push(<React.Fragment key={`t-${kwi}-${ni}-${pi}`}>{part}</React.Fragment>);
        }
      });
    });
    nodes = next;
  });
  return <>{nodes}</>;
}

function postShortId(post: FbPost): string {
  const parts = post.id.split('_');
  return parts[1] || post.id;
}

export function PostCard({
  post,
  groupNames,
  category,
  keywords,
  pages,
  leads,
  replySuggestion,
  commentSummary,
  onOpenLightbox,
  onSuggestReply,
  onSummarizeComments,
  onCommentSent,
}: {
  post: FbPost;
  groupNames: Record<string, string>;
  category?: string;
  keywords: string[];
  pages: FbPage[];
  leads?: Lead[];
  replySuggestion?: ReplySuggestion;
  commentSummary?: CommentSummary;
  onOpenLightbox: (src: string) => void;
  onSuggestReply?: (post: FbPost) => Promise<void>;
  onSummarizeComments?: (post: FbPost) => Promise<void>;
  onCommentSent?: () => Promise<void>;
}) {
  const authorName = post.from?.name || 'Ẩn danh';
  const reactions = post.reactions?.summary?.total_count ?? 0;
  const shares = post.shares?.count ?? 0;
  const cData = post.comments || {};
  const cList = cData.data || [];
  const cCount = cData.summary?.total_count ?? cList.length;
  const text = post.message || '';
  const long = text.length > 300;
  const pid = postShortId(post);
  const gid = post._group_id || '';
  const gName = gid && groupNames[gid] ? groupNames[gid] : gid;

  const [expanded, setExpanded] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [cmtOpen, setCmtOpen] = useState(false);
  const [cmtMsg, setCmtMsg] = useState('');
  const [sending, setSending] = useState(false);
  const [pageId, setPageId] = useState('');
  const [suggestBusy, setSuggestBusy] = useState(false);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [uploadingImage, setUploadingImage] = useState(false);
  const postLeads = leads || [];
  const visibleCommentSummary =
    commentSummary && !((commentSummary.fetched_comment_count ?? 0) === 0 && cCount > 0)
      ? commentSummary
      : undefined;

  const atts = (post.attachments?.data || []).map((a, i) => {
    if (a.type === 'photo') {
      const src = a.media?.image?.src || '';
      return src ? (
        <div key={i} className="attachment">
          <img src={src} alt="" loading="lazy" onClick={() => onOpenLightbox(src)} />
        </div>
      ) : null;
    }
    if (a.type === 'video') {
      const src = a.media?.source || '';
      return src ? (
        <div key={i} className="attachment attachment-link">
          🎥{' '}
          <a href={src} target="_blank" rel="noreferrer">
            Xem video
          </a>
        </div>
      ) : null;
    }
    if (a.type === 'share' || a.type === 'link') {
      const url = a.url || '';
      return url ? (
        <div key={i} className="attachment attachment-link">
          🔗{' '}
          <a href={url} target="_blank" rel="noreferrer">
            {url.substring(0, 60)}…
          </a>
        </div>
      ) : null;
    }
    return null;
  });

  async function sendComment() {
    const ta = document.querySelector<HTMLTextAreaElement>(`textarea[data-cmt="${post.id}"]`);
    const message = ta?.value.trim() || '';
    const image = imageUrl.trim();
    if (!message && !image) return;
    setSending(true);
    setCmtMsg('⏳ Đang gửi…');
    try {
      const r = await api('/api/comment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          post_id: post.id,
          group_id: gid,
          post_url: post.permalink_url || '',
          message,
          image_url: image,
          page_id: pageId,
        }),
      });
      const d = await r.json();
      if (d.ok) {
        if (ta) ta.value = '';
        setImageUrl('');
        setCmtMsg(image ? '✅ Đã bình luận kèm ảnh!' : '✅ Đã bình luận!');
        await onCommentSent?.();
      } else setCmtMsg('❌ ' + (d.error || 'Lỗi'));
    } catch {
      setCmtMsg('❌ Lỗi kết nối');
    }
    setSending(false);
    setTimeout(() => setCmtMsg(''), 4000);
  }

  async function uploadCommentImage(file?: File) {
    if (!file) return;
    setUploadingImage(true);
    setCmtMsg('⏳ Đang upload ảnh...');
    try {
      const fd = new FormData();
      fd.append('image', file);
      const r = await api('/api/uploads/comment-image', {
        method: 'POST',
        body: fd,
      });
      const d = await r.json();
      if (d.ok && d.image_url) {
        setImageUrl(d.image_url);
        setCmtMsg('✅ Đã upload ảnh');
      } else {
        setCmtMsg('❌ ' + (d.error || 'Upload ảnh lỗi'));
      }
    } catch {
      setCmtMsg('❌ Lỗi upload ảnh');
    }
    setUploadingImage(false);
    setTimeout(() => setCmtMsg(''), 3500);
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="avatar" style={{ background: avatarColor(authorName) }}>
          {initials(authorName)}
        </div>
        <div className="author-info">
          <div className="author-name">{authorName}</div>
          <div className="post-meta">
            <span className="meta-time">{timeAgo(post.created_time)}</span>
            <span className="meta-dot" />
            {post.is_hidden ? (
              <span className="badge badge-pending">⏳ Chờ duyệt</span>
            ) : (
              <span className="badge badge-ok">✅ Đã đăng</span>
            )}
            {gid ? (
              <>
                <span className="meta-dot" />
                <span className="badge badge-group" title={`${gName}\nID: ${gid}`}>
                  📋 {gName}
                </span>
              </>
            ) : null}
            {category ? (
              <>
                <span className="meta-dot" />
                <span className="badge badge-cat" style={{ background: catBg(category), color: catFg(category) }}>
                  🏷️ {category}
                </span>
              </>
            ) : null}
            {postLeads.length ? (
              <>
                <span className="meta-dot" />
                <span className="badge badge-lead">🧲 {postLeads.length} lead</span>
              </>
            ) : null}
            {replySuggestion ? (
              <>
                <span className="meta-dot" />
                <span className="badge badge-reply">🤖 Gợi ý</span>
              </>
            ) : null}
            {visibleCommentSummary ? (
              <>
                <span className="meta-dot" />
                <span className="badge badge-reply">📊 Đã tóm tắt</span>
              </>
            ) : null}
          </div>
        </div>
      </div>
      {text ? (
        <div className="card-body">
          <div className={`post-text${long && !expanded ? ' collapsed' : ''}`} id={`pt-${pid}`}>
            <HighlightText text={text} keywords={keywords} />
          </div>
          {long && !expanded ? (
            <span className="see-more" onClick={() => setExpanded(true)} role="button" tabIndex={0}>
              Xem thêm ▾
            </span>
          ) : null}
        </div>
      ) : null}
      {atts.some(Boolean) ? <div className="card-body" style={{ paddingTop: 0 }}>{atts}</div> : null}
      <div className="card-stats">
        <div className="stat">
          <span className="stat-icon">❤️</span> {reactions}
        </div>
        <div className="stat">
          <span className="stat-icon">💬</span> {cCount}
        </div>
        <div className="stat">
          <span className="stat-icon">↗️</span> {shares}
        </div>
      </div>
      {cCount > 0 ? (
        <div className="comments-wrap">
          <span className="comments-toggle" onClick={() => setCommentsOpen((o) => !o)} role="button" tabIndex={0}>
            💬 {cCount} bình luận {commentsOpen ? '▴' : '▾'}
          </span>
          {commentsOpen ? (
            <div className="comments-list">
              {cList.length ? (
                cList.map((c, i) => {
                  const cn = c.from?.name || 'Ẩn danh';
                  return (
                    <div key={i} className="comment">
                      <div className="comment-av">{initials(cn)}</div>
                      <div className="comment-bubble">
                        <div className="comment-name">{cn}</div>
                        <div className="comment-msg">{c.message || ''}</div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div style={{ fontSize: 13, color: '#65676b' }}>Không có bình luận</div>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
      <LeadBlock items={postLeads} />
      {replySuggestion ? <ReplySuggestionBlock item={replySuggestion} /> : null}
      {visibleCommentSummary ? <CommentSummaryBlock item={visibleCommentSummary} /> : null}
      <div className="card-footer">
        <div className="post-link">
          <a href={post.permalink_url || '#'} target="_blank" rel="noreferrer">
            🔗 Xem trên Facebook
          </a>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {onSuggestReply ? (
            <button
              type="button"
              className="btn-reply-ai"
              disabled={suggestBusy}
              onClick={async () => {
                setSuggestBusy(true);
                try {
                  await onSuggestReply(post);
                } finally {
                  setSuggestBusy(false);
                }
              }}
            >
              {suggestBusy ? '⏳ AI đang đọc...' : '🤖 Gợi ý trả lời'}
            </button>
          ) : null}
          {onSummarizeComments ? (
            <button
              type="button"
              className="btn-reply-ai"
              disabled={summaryBusy}
              onClick={async () => {
                setSummaryBusy(true);
                try {
                  await onSummarizeComments(post);
                } finally {
                  setSummaryBusy(false);
                }
              }}
            >
              {summaryBusy ? '⏳ Đang tóm tắt...' : '📊 Tóm tắt CMT'}
            </button>
          ) : null}
          <button type="button" className="btn-write-comment" onClick={() => setCmtOpen((o) => !o)}>
            {cmtOpen ? '✖ Đóng' : '✏️ Bình luận'}
          </button>
        </div>
      </div>
      <div className={`comment-box${cmtOpen ? ' open' : ''}`}>
        <textarea className="comment-textarea" rows={2} placeholder="Nhập bình luận..." data-cmt={post.id} />
        <div className="comment-file-row">
          <label className={`btn-image-upload${uploadingImage ? ' disabled' : ''}`}>
            📎 Upload ảnh
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              disabled={uploadingImage}
              onChange={(e) => void uploadCommentImage(e.target.files?.[0])}
            />
          </label>
          <span className="comment-file-hint">JPG, PNG, WEBP, GIF tối đa 8MB</span>
        </div>
        <input
          className="comment-image-input"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          placeholder="URL ảnh public sau khi upload hoặc dán link ảnh"
        />
        {imageUrl ? (
          <div className="comment-image-preview">
            <img src={imageUrl} alt="Ảnh bình luận" />
            <button type="button" onClick={() => setImageUrl('')}>
              Gỡ ảnh
            </button>
          </div>
        ) : null}
        <div className="comment-row">
          <select className="comment-as" value={pageId} onChange={(e) => setPageId(e.target.value)}>
            <option value="">👤 Cá nhân</option>
            {pages.map((p) => (
              <option key={p.id} value={p.id}>
                📄 {p.name}
              </option>
            ))}
          </select>
          <button type="button" className="btn-send" disabled={sending} onClick={() => void sendComment()}>
            Gửi
          </button>
          <span className="comment-msg-result">{cmtMsg}</span>
        </div>
      </div>
    </div>
  );
}
