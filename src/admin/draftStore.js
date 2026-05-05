// localStorage-backed draft autosave for the Posts editor.
// Pure helpers so they're trivial to unit-test; PostEditor binds the
// debounced save loop + recovery banner.

const PREFIX = 'bl.admin.draft.';

function key(id) {
  return PREFIX + (id || '__new__');
}

export function saveDraft(id, markdown, savedAt = Date.now()) {
  try {
    const payload = JSON.stringify({ markdown, savedAt });
    localStorage.setItem(key(id), payload);
    return true;
  } catch {
    return false;
  }
}

export function loadDraft(id) {
  try {
    const raw = localStorage.getItem(key(id));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.markdown !== 'string') return null;
    return {
      markdown: parsed.markdown,
      savedAt: typeof parsed.savedAt === 'number' ? parsed.savedAt : 0,
    };
  } catch {
    return null;
  }
}

export function clearDraft(id) {
  try {
    localStorage.removeItem(key(id));
    return true;
  } catch {
    return false;
  }
}

export function draftIsNewerThan(draft, serverIsoOrTs) {
  if (!draft) return false;
  if (!serverIsoOrTs) return true;
  const serverTs = typeof serverIsoOrTs === 'number'
    ? serverIsoOrTs
    : new Date(serverIsoOrTs).getTime();
  if (Number.isNaN(serverTs)) return true;
  return draft.savedAt > serverTs;
}
