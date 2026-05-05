// Pure helpers for the admin keyboard-shortcut layer.
// The hook in `useGlobalShortcuts.js` binds these to window/document.

// Single source of truth for `g <x>` jumps. Order is intentional: appears
// in the help dialog grouped under 跳转.
export const JUMP_MAP = {
  d: { to: '/admin/dashboard', label: '仪表盘' },
  p: { to: '/admin/posts', label: '文章' },
  m: { to: '/admin/media', label: '媒体' },
  c: { to: '/admin/comments', label: '评论' },
  t: { to: '/admin/tags', label: '标签' },
  i: { to: '/admin/inbox', label: '收件箱' },
  n: { to: '/admin/now', label: '近况' },
  a: { to: '/admin/activity-log', label: '活动日志' },
  s: { to: '/admin/settings', label: '设置' },
  e: { to: '/admin/pet', label: '宠物助手' },
};

// Shortcuts shown in the help dialog. Grouped by scope. The hook reads
// the same constants so the dialog never drifts from real behavior.
export const SHORTCUT_GROUPS = [
  {
    scope: '全局',
    items: [
      { keys: ['⌘', 'K'], desc: '打开命令面板' },
      { keys: ['?'], desc: '显示快捷键帮助' },
      { keys: ['Esc'], desc: '关闭对话框 / 返回列表' },
    ],
  },
  {
    scope: '跳转 (g 然后按)',
    items: Object.entries(JUMP_MAP).map(([k, v]) => ({
      keys: ['g', k],
      desc: v.label,
    })),
  },
  {
    scope: '列表页 (文章)',
    items: [
      { keys: ['j'], desc: '下一行' },
      { keys: ['k'], desc: '上一行' },
      { keys: ['Enter'], desc: '编辑当前行' },
      { keys: ['e'], desc: '编辑当前行' },
      { keys: ['n'], desc: '新建文章' },
    ],
  },
];

// True when keystrokes should NOT trigger global shortcuts: user is
// typing into a text surface, or a dialog (palette / modal) is open.
export function shouldIgnoreEvent(e) {
  if (e.metaKey || e.ctrlKey || e.altKey) return true; // let browser/app shortcuts win
  const t = e.target;
  if (!t) return false;
  const tag = t.tagName;
  if (tag === 'TEXTAREA') return true;
  if (tag === 'INPUT') {
    const ty = (t.type || 'text').toLowerCase();
    if (
      ty === 'text' ||
      ty === 'search' ||
      ty === 'email' ||
      ty === 'password' ||
      ty === 'url' ||
      ty === 'number' ||
      ty === 'tel' ||
      ty === 'datetime-local'
    ) {
      return true;
    }
  }
  if (tag === 'SELECT') return true;
  if (t.isContentEditable) return true;
  // Active dialog (.palette-bg, .confirm-bg, [role=dialog]) suppresses
  // global keys so the dialog can own them.
  if (document.querySelector('[data-testid=admin-palette], [data-shortcut-suppress=true]')) {
    return true;
  }
  return false;
}

// Resolve a `g <x>` sequence. Returns the JUMP_MAP entry or null if x is
// not a valid jump letter. Caller is responsible for the timing window.
export function resolveJump(x) {
  if (!x) return null;
  const k = x.toLowerCase();
  return JUMP_MAP[k] || null;
}
