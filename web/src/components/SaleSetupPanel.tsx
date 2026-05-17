'use client';

import { BusinessProfilePanel } from '@/components/BusinessProfilePanel';

type Props = {
  aiProvider: string;
  onProviderChange: (v: string) => void;
  aiAutoClassify: boolean;
  onAutoClassifyChange: (v: boolean) => void;
  aiStatus: string;
  maskedKey: string;
  hasKey: boolean;
  aiKeyEdit: boolean;
  aiKeyInput: string;
  onAiKeyInput: (v: string) => void;
  onToggleKeyEdit: () => void;
  onTestAi: () => void;
  onSaveKey: () => void;
  onDeleteKey: () => void;
};

export function SaleSetupPanel(props: Props) {
  const {
    aiProvider,
    onProviderChange,
    aiAutoClassify,
    onAutoClassifyChange,
    aiStatus,
    maskedKey,
    hasKey,
    aiKeyEdit,
    aiKeyInput,
    onAiKeyInput,
    onToggleKeyEdit,
    onTestAi,
    onSaveKey,
    onDeleteKey,
  } = props;

  return (
    <div className="setup-panel">
      <div className="setup-section">
        <div className="setup-section-title">🤖 AI</div>
        <div className="ai-row">
          <select value={aiProvider} onChange={(e) => onProviderChange(e.target.value)}>
            <option value="gemini">Google Gemini</option>
            <option value="openai">OpenAI</option>
            <option value="claude">Claude</option>
          </select>
          <button type="button" className="btn-ai-sm btn-ai-test" onClick={() => void onTestAi()}>
            🔌 Test
          </button>
          <label className="ai-auto-label">
            <input type="checkbox" checked={aiAutoClassify} onChange={(e) => onAutoClassifyChange(e.target.checked)} /> Tự động
          </label>
        </div>
        <div className="ai-row">
          <span className="ai-key-label">API Key</span>
          <span className="ai-key-display">{hasKey ? maskedKey : 'Chưa có key'}</span>
          {aiKeyEdit ? (
            <>
              <input
                className="ai-key-input"
                placeholder="Nhập API Key..."
                value={aiKeyInput}
                onChange={(e) => onAiKeyInput(e.target.value)}
              />
              <button type="button" className="btn-ai-sm btn-ai-save" onClick={() => void onSaveKey()}>
                💾
              </button>
            </>
          ) : null}
          {hasKey ? (
            <button type="button" className="btn-ai-sm btn-ai-del" onClick={() => void onDeleteKey()}>
              🗑️
            </button>
          ) : null}
          <button type="button" className="btn-ai-sm btn-ai-test" onClick={onToggleKeyEdit}>
            {hasKey ? '✏️' : '➕'}
          </button>
        </div>
        {aiStatus ? <div className="setup-hint">{aiStatus}</div> : null}
      </div>

      <div className="setup-divider" />

      <BusinessProfilePanel embedded />
    </div>
  );
}
