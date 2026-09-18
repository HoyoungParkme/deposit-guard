/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        fg: 'var(--fg)',
        muted: 'var(--muted)',
        line: 'var(--line)',
        primary: 'var(--primary)',
        safe: 'var(--safe)',
        'safe-bg': 'var(--safe-bg)',
        caution: 'var(--caution)',
        'caution-bg': 'var(--caution-bg)',
        danger: 'var(--danger)',
        'danger-bg': 'var(--danger-bg)',
        highlight: 'var(--highlight)',
      },
    },
  },
  plugins: [],
};
