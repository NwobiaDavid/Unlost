import type { UnlostBridge } from './index'

declare global {
  interface Window {
    unlost: UnlostBridge
  }
}

export {}
