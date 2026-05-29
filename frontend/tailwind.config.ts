import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: 'rgb(var(--bg) / <alpha-value>)',
        bg2: 'rgb(var(--bg2) / <alpha-value>)',
        bg3: 'rgb(var(--bg3) / <alpha-value>)',
        text: 'rgb(var(--text) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
        accentHover: 'rgb(var(--accent-hover) / <alpha-value>)',
        own: 'rgb(var(--own) / <alpha-value>)',
        ownText: 'rgb(var(--own-text) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
        danger: 'rgb(var(--danger) / <alpha-value>)',
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      animation: {
        'slide-in-right': 'slide-in-right 250ms cubic-bezier(0.4, 0, 0.2, 1)',
        'slide-out-right': 'slide-out-right 250ms cubic-bezier(0.4, 0, 0.2, 1)',
        'fade-in': 'fade-in 200ms ease-out',
        'pulse-dot': 'pulse-dot 1.4s infinite ease-in-out',
        'msg-in-own': 'msg-in-own 220ms cubic-bezier(0.34, 1.56, 0.64, 1)',
        'msg-in-other': 'msg-in-other 220ms cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      keyframes: {
        'slide-in-right': {
          from: { transform: 'translateX(100%)' },
          to: { transform: 'translateX(0)' },
        },
        'slide-out-right': {
          from: { transform: 'translateX(0)' },
          to: { transform: 'translateX(100%)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'pulse-dot': {
          '0%, 80%, 100%': { opacity: '0.3', transform: 'scale(0.8)' },
          '40%': { opacity: '1', transform: 'scale(1)' },
        },
        'msg-in-own': {
          from: { opacity: '0', transform: 'translate(8px, 4px) scale(0.95)' },
          to: { opacity: '1', transform: 'translate(0, 0) scale(1)' },
        },
        'msg-in-other': {
          from: { opacity: '0', transform: 'translate(-8px, 4px) scale(0.95)' },
          to: { opacity: '1', transform: 'translate(0, 0) scale(1)' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
