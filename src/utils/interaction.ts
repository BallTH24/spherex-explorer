export interface InteractionState {
  hover: boolean;
  drag: boolean;
}
export function applyCursor(el: HTMLElement, s: InteractionState): void {
  el.style.cursor = s.drag ? 'grabbing' : s.hover ? 'pointer' : 'grab';
}
