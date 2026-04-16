/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        gray: {
          950: '#030712',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        /** Soft green “opportunity” glow — STRONG BUY */
        'action-strong-buy': 'actionStrongBuy 2.4s ease-in-out infinite',
        /** Moderate red pulse — SELL */
        'action-sell': 'actionSell 2s ease-in-out infinite',
        /** Faster, stronger red glow — STRONG SELL */
        'action-strong-sell': 'actionStrongSell 1.2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        actionStrongBuy: {
          '0%, 100%': {
            boxShadow: '0 0 0 0 rgba(34, 197, 94, 0)',
            borderColor: 'rgba(34, 197, 94, 0.35)',
          },
          '50%': {
            boxShadow: '0 0 14px 3px rgba(34, 197, 94, 0.4)',
            borderColor: 'rgba(34, 197, 94, 0.65)',
          },
        },
        actionSell: {
          '0%, 100%': {
            boxShadow: '0 0 0 0 rgba(248, 113, 113, 0)',
            borderColor: 'rgba(239, 68, 68, 0.35)',
          },
          '50%': {
            boxShadow: '0 0 10px 2px rgba(248, 113, 113, 0.35)',
            borderColor: 'rgba(239, 68, 68, 0.65)',
          },
        },
        actionStrongSell: {
          '0%, 100%': {
            boxShadow: '0 0 0 0 rgba(239, 68, 68, 0)',
            borderColor: 'rgba(239, 68, 68, 0.45)',
          },
          '50%': {
            boxShadow: '0 0 18px 5px rgba(239, 68, 68, 0.5)',
            borderColor: 'rgba(248, 113, 113, 0.85)',
          },
        },
      },
    },
  },
  plugins: [],
}
