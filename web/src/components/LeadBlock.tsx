'use client';

import type { Lead } from '@/lib/types';
import { pct } from '@/lib/format';

export function LeadBlock({ items }: { items: Lead[] }) {
  if (!items.length) return null;

  return (
    <div className="lead-wrap">
      <div className="lead-head">
        <span>🧲 Nhu cầu phát hiện</span>
        <span>{items.length}</span>
      </div>
      <div className="lead-list">
        {items.map((lead, i) => {
          const source = lead.source === 'post' ? 'Bài viết' : 'Bình luận';
          const conf = pct(lead.confidence);
          return (
            <div key={i} className="lead-item">
              <div className="lead-main">
                <span className="lead-name">{lead.name || 'Ẩn danh'}</span>
                <span className="lead-source">{source}</span>
                {lead.phone ? (
                  <span className="lead-phone">☎ {lead.phone}</span>
                ) : (
                  <span className="lead-no-phone">Chưa có SĐT</span>
                )}
              </div>
              <div className="lead-need">{lead.need || ''}</div>
              <div className="lead-sub">
                {lead.product_or_service ? <span>{lead.product_or_service}</span> : null}
                {lead.location ? <span>{lead.location}</span> : null}
                {lead.budget ? <span>{lead.budget}</span> : null}
                {conf ? <span>Độ chắc {conf}</span> : null}
              </div>
              {lead.evidence ? <div className="lead-evidence">&quot;{lead.evidence}&quot;</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
