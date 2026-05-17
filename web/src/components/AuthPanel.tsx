'use client';

import { useState } from 'react';

type Props = {
  mode: 'login' | 'setup';
  status: string;
  onLogin: (username: string, password: string) => Promise<void>;
  onSetup: (payload: { name: string; username: string; password: string; cookie: string }) => Promise<void>;
};

export function AuthPanel({ mode, status, onLogin, onSetup }: Props) {
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [cookie, setCookie] = useState('');
  const isSetup = mode === 'setup';

  async function submit() {
    if (isSetup) {
      await onSetup({ name, username, password, cookie });
    } else {
      await onLogin(username, password);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-title">{isSetup ? 'Setup tài khoản đầu tiên' : 'Đăng nhập'}</div>
        <div className="auth-sub">
          {isSetup
            ? 'Tài khoản đầu tiên là admin. Sau đó admin thêm nhân sự, mỗi người có cookie Facebook riêng.'
            : 'Mỗi nhân sự dùng tài khoản riêng. Cookie Facebook sẽ tự gắn theo tài khoản đăng nhập.'}
        </div>
        {isSetup ? (
          <div className="auth-field">
            <label>Tên nhân sự</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ví dụ: Sale A" />
          </div>
        ) : null}
        <div className="auth-field">
          <label>Tài khoản đăng nhập</label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            onKeyDown={(e) => e.key === 'Enter' && void submit()}
          />
        </div>
        <div className="auth-field">
          <label>Mật khẩu</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isSetup ? 'new-password' : 'current-password'}
            onKeyDown={(e) => e.key === 'Enter' && void submit()}
          />
        </div>
        {isSetup ? (
          <div className="auth-field">
            <label>Cookie Facebook</label>
            <textarea value={cookie} onChange={(e) => setCookie(e.target.value)} placeholder="Dán cookie có c_user=..." />
          </div>
        ) : null}
        <div className="auth-actions">
          <button type="button" className="btn btn-primary" onClick={() => void submit()}>
            {isSetup ? 'Tạo admin' : 'Đăng nhập'}
          </button>
        </div>
        {status ? <div className="auth-status">{status}</div> : null}
      </div>
    </div>
  );
}
