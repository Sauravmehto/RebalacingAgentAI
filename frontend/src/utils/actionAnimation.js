/**
 * Optional Tailwind classes for motion on high-signal actions.
 * Keyframes live in tailwind.config.js; `motion-reduce:animate-none` respects OS settings.
 */
export function actionAnimationClass(action) {
  switch (action) {
    case 'STRONG BUY':
      return 'animate-action-strong-buy motion-reduce:animate-none'
    case 'SELL':
      return 'animate-action-sell motion-reduce:animate-none'
    case 'STRONG SELL':
      return 'animate-action-strong-sell motion-reduce:animate-none'
    default:
      return ''
  }
}
