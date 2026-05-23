import { ImageResponse } from 'next/og';

export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background:
            'radial-gradient(circle at 50% 30%, #221d52 0%, #0f0a2e 60%, #050314 100%)',
        }}
      >
        <div
          style={{
            position: 'relative',
            width: 156,
            height: 156,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              background:
                'radial-gradient(circle at 36% 30%, #2a2566 0%, #14102e 70%, #050314 100%)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              inset: 14,
              borderRadius: '50%',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              inset: 26,
              borderRadius: '50%',
              border: '1px solid rgba(255,255,255,0.07)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              inset: 38,
              borderRadius: '50%',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          />
          <div
            style={{
              width: 58,
              height: 58,
              borderRadius: '50%',
              background:
                'linear-gradient(135deg, #818cf8 0%, #6366f1 55%, #f43f5e 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 0 1px rgba(255,255,255,0.25)',
            }}
          >
            <div
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#050314',
              }}
            />
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
