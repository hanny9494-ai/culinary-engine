import React, { useState } from 'react';

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue('');
  };

  return (
    <div style={{ display: 'flex', borderTop: '1px solid #1a1a2e', background: '#0d0d18' }}>
      <span style={{ padding: '6px 4px 6px 8px', color: '#4a6cf7', fontFamily: 'SF Mono, Menlo, monospace', fontSize: 12 }}>$</span>
      <input
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSubmit(); } }}
        disabled={disabled}
        placeholder=""
        style={{
          flex: 1, background: 'transparent', color: '#ccc', border: 'none',
          padding: '6px 4px', fontSize: 12, fontFamily: 'SF Mono, Menlo, monospace',
          outline: 'none',
        }}
      />
    </div>
  );
}
