const read = async (path) => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Impossible de charger ${path}`);
  return response.text();
};

const [main, panels, core, view] = await Promise.all([
  read(new URL('./template-main.html', import.meta.url)),
  read(new URL('./template-panels.html', import.meta.url)),
  read(new URL('./controller-core.js', import.meta.url)),
  read(new URL('./controller-view.js', import.meta.url)),
]);

const root = document.createElement('x-dc');
const translateTemplate = (html) => {
  const keys = globalThis.MESSENGER_I18N.keys;
  const replace = (text) => {
    const trimmed = text.trim();
    const index = keys.indexOf(trimmed);
    return index < 0 ? text : text.replace(trimmed, '{{ ui.t' + index + ' }}');
  };
  return html.replace(/>([^<>]+)</g, (_, text) => '>' + text.split(/(\{\{[^}]+\}\})/).map((part) => part.startsWith('{{') ? part : replace(part)).join('') + '<')
    .replace(/(title|placeholder|aria-label)="([^"{]+)"/g, (_, attr, text) => attr + '="' + replace(text) + '"');
};
root.innerHTML = translateTemplate(main + panels).replace(/<(div|span)([^>]*onClick="[^>]+)>/g, (_, tag, attrs) => '<' + tag + attrs + (attrs.includes('role=') || attrs.includes('onClick="{{ stop }}"') ? '>' : ' role="button" tabindex="0">'));
document.addEventListener('keydown', (event) => {
  const modal = document.querySelector('[role="dialog"]');
  if (modal && event.key === 'Escape') { event.preventDefault(); modal.querySelector('[data-modal-close]')?.click(); return; }
  if (modal && event.key === 'Tab') {
    const controls = [...modal.querySelectorAll('input,textarea,select,button,a[href],[tabindex="0"]')].filter(el => !el.disabled && el.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (!first) { event.preventDefault(); modal.focus(); return; }
    if (!modal.contains(document.activeElement) || (!event.shiftKey && document.activeElement === last) || (event.shiftKey && document.activeElement === first)) {
      event.preventDefault(); (event.shiftKey ? last : first).focus(); return;
    }
  }
  if (event.target.closest('input,textarea,select,button,a,[contenteditable="true"]')) return;
  const button = event.target.closest('[role="button"]');
  if (button && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); button.click(); }
});
document.body.prepend(root);
let openDialog = null, previousFocus = null;
new MutationObserver(() => {
  const modal = document.querySelector('[role="dialog"]');
  if (modal === openDialog) return;
  if (modal) {
    if (!openDialog) previousFocus = document.activeElement;
    openDialog = modal;
    (modal.querySelector('[tabindex="0"],button,input') || modal).focus();
  } else { openDialog = null; if (previousFocus?.isConnected) previousFocus.focus(); }
}).observe(document.body, { childList:true, subtree:true });

const controller = document.createElement('script');
controller.type = 'text/x-dc';
controller.dataset.dcScript = '';
controller.dataset.props = JSON.stringify({ $preview: { width: 1480, height: 960 } });
controller.textContent = core + view;
document.body.append(controller);

const support = document.createElement('script');
support.src = './support.js';
document.head.append(support);
