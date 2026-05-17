'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { BusinessProfile } from '@/lib/types';

const emptyProfile = (): BusinessProfile => ({
  business_name: '',
  phone: '',
  address: '',
  why_choose_us: '',
  extra_notes: '',
});

export function BusinessProfilePanel({ embedded = false }: { embedded?: boolean }) {
  const [profile, setProfile] = useState<BusinessProfile>(emptyProfile());
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api('/api/business-profile');
      const d = await r.json();
      if (d.ok) {
        setProfile({ ...emptyProfile(), ...(d.profile || {}) });
        if (d.storage === 'supabase') setStatus('Đã nạp Supabase');
      }
    } catch {
      setStatus('Không tải được thông tin');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function update(field: keyof BusinessProfile, value: string) {
    setProfile((p) => ({ ...p, [field]: value }));
  }

  async function save() {
    setStatus('Đang lưu...');
    try {
      const r = await api('/api/business-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      const d = await r.json();
      if (d.ok) {
        setProfile({ ...emptyProfile(), ...(d.profile || profile) });
        setStatus(d.storage === 'supabase' ? '✅ Đã lưu Supabase' : '✅ Đã lưu local');
        if (d.warning) setTimeout(() => setStatus(`⚠️ ${d.warning}`), 1200);
        else setTimeout(() => setStatus(''), 5000);
      } else {
        setStatus(`❌ ${d.error || 'Lỗi lưu'}`);
      }
    } catch {
      setStatus('❌ Lỗi kết nối');
    }
  }

  async function generateText() {
    if (!Object.values(profile).some(Boolean)) {
      setStatus('Nhập thông tin trước khi tạo');
      return;
    }
    setBusy(true);
    setStatus('AI đang tạo văn bản...');
    try {
      const r = await api('/api/business-profile/generate-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      const d = await r.json();
      if (d.ok) {
        setProfile({ ...emptyProfile(), ...(d.profile || profile) });
        setStatus(d.storage === 'supabase' ? '✅ AI đã tạo và lưu Supabase' : '✅ AI đã tạo và lưu local');
        if (d.warning) setTimeout(() => setStatus(`⚠️ ${d.warning}`), 1200);
        else setTimeout(() => setStatus(''), 7000);
      } else {
        setStatus(`❌ ${d.error || 'AI chưa tạo được văn bản'}`);
      }
    } catch {
      setStatus('❌ Lỗi kết nối');
    }
    setBusy(false);
  }

  const titleClass = embedded ? 'setup-section-title' : 'panel-label';
  const body = (
    <>
      <div className="ai-row">
        <div className={titleClass}>🏪 Bên mình</div>
        <div style={{ flex: 1 }} />
        <button type="button" className="btn-ai-sm btn-ai-test" disabled={busy} onClick={() => void generateText()}>
          {busy ? '⏳ AI đang viết...' : '✨ AI tạo văn bản'}
        </button>
        <button type="button" className="btn-ai-sm btn-ai-save" onClick={() => void save()}>
          💾 Lưu
        </button>
        <span className="profile-status">{status}</span>
      </div>
      <div className="ai-row">
        <div className="profile-grid">
          <div className="profile-field">
            <label>Tên / thương hiệu</label>
            <input
              type="text"
              value={profile.business_name || ''}
              placeholder="Tên bên mình"
              onChange={(e) => update('business_name', e.target.value)}
            />
          </div>
          <div className="profile-field">
            <label>Số điện thoại</label>
            <input
              type="text"
              value={profile.phone || ''}
              placeholder="SĐT tư vấn"
              onChange={(e) => update('phone', e.target.value)}
            />
          </div>
          <div className="profile-field full">
            <label>Địa chỉ</label>
            <input
              type="text"
              value={profile.address || ''}
              placeholder="Địa chỉ cửa hàng / văn phòng"
              onChange={(e) => update('address', e.target.value)}
            />
          </div>
          <div className="profile-field full">
            <label>Lý do chọn mình</label>
            <textarea
              value={profile.why_choose_us || ''}
              placeholder="Ví dụ: tư vấn nhanh, hàng sẵn, bảo hành rõ ràng..."
              onChange={(e) => update('why_choose_us', e.target.value)}
            />
          </div>
          <div className="profile-field full">
            <label>Ghi chú thêm</label>
            <textarea
              value={profile.extra_notes || ''}
              placeholder="Thông tin sale cần nhớ khi trả lời khách"
              onChange={(e) => update('extra_notes', e.target.value)}
            />
          </div>
        </div>
      </div>
    </>
  );

  if (embedded) {
    return <div className="setup-section">{body}</div>;
  }
  return <div className="ai-panel">{body}</div>;
}
