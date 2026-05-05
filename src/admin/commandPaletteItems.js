// Pure helpers for the admin command palette.
// Kept separate from CommandPalette.jsx so the filtering / item-building
// logic is trivial to unit-test without rendering React.

export function buildPaletteItems({
  navGroups,
  posts = [],
  runners,
  currentPath,
}) {
  const NAV_ICON = '→';
  const CMD_ICON = '⌥';
  const POST_ICON = '✦';

  const nav = [];
  for (const g of navGroups || []) {
    for (const it of g.items || []) {
      // Don't suggest the page the user is already on.
      if (it.to === currentPath) continue;
      nav.push({
        type: 'nav',
        ico: NAV_ICON,
        label: it.label,
        sub: `${g.n} · ${g.label}`,
        run: () => runners.go(it.to),
      });
    }
  }

  const cmds = [
    {
      type: 'cmd',
      ico: CMD_ICON,
      label: '新建文章',
      sub: 'posts',
      run: () => runners.newPost(),
    },
    {
      type: 'cmd',
      ico: CMD_ICON,
      label: '复制访问令牌',
      sub: 'auth',
      run: () => runners.copyToken(),
    },
    {
      type: 'cmd',
      ico: CMD_ICON,
      label: '查看公网首页',
      sub: 'site',
      run: () => runners.openPublic(),
    },
    {
      type: 'cmd',
      ico: CMD_ICON,
      label: '退出登录',
      sub: 'auth',
      run: () => runners.logout(),
    },
  ];

  const postItems = (posts || []).map((p) => ({
    type: 'post',
    ico: POST_ICON,
    label: p.title || `(无标题) ${p.id}`,
    sub: `id: ${p.id}${p.tag ? ' · ' + p.tag : ''}`,
    run: () => runners.openPost(p.id),
  }));

  return [...nav, ...cmds, ...postItems];
}

export function filterPaletteItems(items, q) {
  if (!q) return items;
  const qq = q.toLowerCase();
  return items.filter((it) =>
    it.label.toLowerCase().includes(qq) ||
    (it.sub || '').toLowerCase().includes(qq),
  );
}

export function groupBySection(items) {
  const out = { nav: [], cmd: [], post: [] };
  items.forEach((it, idx) => {
    if (out[it.type]) out[it.type].push({ it, idx });
  });
  return out;
}
