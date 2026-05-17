'use client';

import { useState } from 'react';
import type { StaffAccount } from '@/lib/types';

type Props = {
  staff: StaffAccount[];
  currentStaff?: StaffAccount | null;
  canManage: boolean;
  status: string;
  onAdd: (payload: { name: string; username: string; password: string; cookie: string }) => Promise<void>;
  onDelete: (staffId: string) => Promise<void>;
};

export function StaffCookiePanel({ staff, currentStaff, canManage, status, onAdd, onDelete }: Props) {
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [cookie, setCookie] = useState('');

  async function addStaff() {
    await onAdd({ name, username, password, cookie });
    setName('');
    setUsername('');
    setPassword('');
    setCookie('');
  }

  return (
    <div className="setup-section">
      <div className="setup-section-title">🍪 Cookie nhân sự</div>
      {canManage ? (
        <div className="staff-form">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên nhân sự" />
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Mật khẩu" />
          <textarea value={cookie} onChange={(e) => setCookie(e.target.value)} placeholder="Dán cookie Facebook có c_user=..." />
          <button type="button" className="btn-ai-sm btn-ai-save" onClick={() => void addStaff()}>
            💾 Thêm nhân sự
          </button>
        </div>
      ) : (
        <div className="setup-hint">Cookie của bạn do admin cấu hình, không tự sửa tại đây.</div>
      )}
      <div className="staff-list">
        {staff.length ? (
          staff.map((item) => {
            const active = item.id && currentStaff?.id === item.id;
            return (
              <div key={item.id || item.username} className="staff-item">
                <div className="staff-main">
                  <div className="staff-name">
                    {item.name || 'Chưa đặt tên'}
                    {active ? <span className="staff-badge">Đang dùng</span> : null}
                    <span className="staff-badge">{item.role === 'admin' ? 'admin' : 'nhân sự'}</span>
                  </div>
                  <div className="staff-meta">
                    @{item.username || ''} · Facebook ID: {item.facebook_user_id || 'chưa đọc được'} · {item.cookie_masked || ''}
                  </div>
                </div>
                {canManage && !active && item.id ? (
                  <button type="button" className="btn-ai-sm btn-ai-del" onClick={() => void onDelete(item.id!)}>
                    Xoá
                  </button>
                ) : null}
              </div>
            );
          })
        ) : (
          <div className="setup-hint">Chưa có nhân sự.</div>
        )}
      </div>
      {status ? <div className="setup-hint">{status}</div> : null}
    </div>
  );
}
