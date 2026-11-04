import { useState } from 'react';

export function UploadPanel({
  disabled,
  notice,
  closedReason,
  onFile,
}: {
  disabled: boolean;
  notice: string;
  closedReason?: string;
  onFile: (file: File) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  function choose(files: FileList | null) {
    if (disabled || !files?.length) return;
    if (files.length !== 1) {
      setError('Choose one ad or script at a time.');
      return;
    }
    setError('');
    onFile(files[0]);
  }
  return (
    <section
      className={`slot${dragging && !disabled ? ' dragging' : ''}`}
      aria-label="Upload workspace"
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        choose(event.dataTransfer.files);
      }}
    >
      <div className="upload-symbol" aria-hidden="true">
        <svg
          width="152"
          height="112"
          viewBox="0 0 152 112"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <rect
            x="32"
            y="16"
            width="72"
            height="84"
            rx="3"
            transform="rotate(-9 32 16)"
            fill="var(--raised)"
          />
          <rect x="43" y="10" width="72" height="84" rx="3" fill="var(--sheet)" />
          <path d="M55 27h35m-35 9h46m-46 9h30m-30 18h44m-44 9h34" stroke="var(--control)" />
          <path d="M52 43c9-3 24-4 36-2l1 8c-15-1-26 0-37 1z" fill="var(--hl)" stroke="none" />
          <path d="M55 45h30" />
          <circle cx="113" cy="78" r="18" fill="var(--sheet)" />
          <path d="M113 86V70m-6 6 6-6 6 6" />
        </svg>
      </div>
      <div className="upload-heading">
        <h2>Upload an ad</h2>
        <p>Choose a script, image or video to screen.</p>
      </div>
      <label className="file-button primary">
        Choose ad or script <span aria-hidden="true">↗</span>
        <input
          aria-label="Upload ad"
          type="file"
          accept=".txt,.md,text/plain,text/markdown,image/png,image/jpeg,image/webp,video/mp4,video/webm,video/quicktime"
          disabled={disabled}
          onChange={(event) => {
            choose(event.target.files);
            event.target.value = '';
          }}
        />
      </label>
      <p className="drop-hint">or drag one file here</p>
      <p className="upload-notice">{notice}</p>
      {closedReason && <p role="status">{closedReason}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
