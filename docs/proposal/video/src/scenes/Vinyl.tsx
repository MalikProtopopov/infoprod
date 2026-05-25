/**
 * SVG-логотип Grammy — виниловая пластинка.
 * Используется в Cover и CTA.
 */
export const Vinyl: React.FC<{ size: number; spin?: number }> = ({ size, spin = 0 }) => {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      style={{ transform: `rotate(${spin}deg)`, transformOrigin: 'center' }}
    >
      <defs>
        <radialGradient id="vinyl-disc" cx="50%" cy="50%" r="55%">
          <stop offset="0%" stopColor="#1e1b4b" />
          <stop offset="70%" stopColor="#0f0a2e" />
          <stop offset="100%" stopColor="#050314" />
        </radialGradient>
        <linearGradient id="vinyl-label" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="55%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#f43f5e" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill="url(#vinyl-disc)" />
      <g stroke="#fff" fill="none" strokeWidth="0.35">
        <circle cx="32" cy="32" r="26" opacity="0.10" />
        <circle cx="32" cy="32" r="23" opacity="0.10" />
        <circle cx="32" cy="32" r="20" opacity="0.10" />
        <circle cx="32" cy="32" r="17" opacity="0.10" />
      </g>
      <path
        d="M 32 3 A 29 29 0 0 1 61 32"
        stroke="#fff"
        strokeWidth="0.8"
        fill="none"
        opacity="0.18"
        strokeLinecap="round"
      />
      <circle cx="32" cy="32" r="11.5" fill="url(#vinyl-label)" />
      <circle cx="32" cy="32" r="1.6" fill="#050314" />
    </svg>
  );
};
