// Admin client for the event_log activity stream.
// Backend: GET /api/admin/activity?type=&limit=&offset=
//          GET /api/admin/dashboard/activity?limit=

import { adminRequest } from './admin.js';

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v == null || v === '') return;
    if (Array.isArray(v)) {
      v.forEach((x) => usp.append(k, String(x)));
    } else {
      usp.append(k, String(v));
    }
  });
  const s = usp.toString();
  return s ? `?${s}` : '';
}

export const activityApi = {
  // Full timeline for /admin/activity-log. `types` is an optional list of
  // event-type strings; leave undefined for "all".
  // Task 45: `q` is a substring filter (server-side ILIKE on actor/target).
  list({ types, q, limit = 50, offset = 0 } = {}) {
    return adminRequest(`/activity${qs({ type: types, q, limit, offset })}`);
  },
  // Dashboard widget — last N events, no filter.
  recent({ limit = 20 } = {}) {
    return adminRequest(`/dashboard/activity${qs({ limit })}`);
  },
};

export default activityApi;
