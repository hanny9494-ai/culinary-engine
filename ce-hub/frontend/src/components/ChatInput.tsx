import React, { useState, useRef } from 'react';

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div style={{ display: 'flex', gap: 8, padding: '8px 12px', borderTop: '1px solid #333', background: '#16162a' }}>
      <textarea
        ref={inputRef}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Send message..."
        rows={1}
        style={{
          flex: 1, background: '#252545', color: '#e0e0e0', border: '1px solid #444',
          borderRadius: 6, padding: '8px 12px', fontSize: 13, resize: 'none',
          fontFamily: 'inherit', outline: 'none',
        }}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        style={{
          background: '#4a6cf7', color: '#fff', border: 'none', borderRadius: 6,
          padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
          opacity: disabled || !value.trim() ? 0.5 : 1,
        }}
      >Send</button>
    </div>
  );
}
