import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  buildQueryFromState,
  buildStateFromQuery,
  statesEqual,
} from './searchParamsState.js';

// React hook that mirrors a typed-state object into the URL querystring
// and back. Mounting reads the URL once. Subsequent state changes go
// through `update` which writes the URL with `replace: false` so
// browser back/forward restores prior views. URL changes (back / forward
// / external nav) push back into state.

export default function useSyncedSearchParams(schema) {
  const navigate = useNavigate();
  const location = useLocation();
  const [state, setState] = useState(() =>
    buildStateFromQuery(location.search, schema),
  );

  // URL → state: rerun whenever the URL search changes (back/forward,
  // external links). Avoids a loop by skipping when the parsed query
  // already matches our local state.
  useEffect(() => {
    const next = buildStateFromQuery(location.search, schema);
    setState((prev) => (statesEqual(prev, next, schema) ? prev : next));
    // schema is stable per page, so depend only on location.search.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  // State → URL: callers use `update(partial)`. We compute the next
  // full state, write the URL, then setState. The URL effect above
  // will see the new search and skip (states match).
  const update = useCallback(
    (partial) => {
      setState((prev) => {
        const next = typeof partial === 'function' ? partial(prev) : { ...prev, ...partial };
        if (statesEqual(prev, next, schema)) return prev;
        const params = buildQueryFromState(next, schema);
        const search = params.toString();
        navigate(
          { pathname: location.pathname, search: search ? '?' + search : '' },
          { replace: false },
        );
        return next;
      });
    },
    [navigate, location.pathname, schema],
  );

  return useMemo(() => [state, update], [state, update]);
}
