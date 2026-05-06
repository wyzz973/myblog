import { useEffect, useState } from 'react';
import { api } from './client.js';

function useResource(loader, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loader()
      .then((v) => {
        if (!cancelled) {
          setData(v);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

export const useSite = () => useResource(() => api.site());
export const useProfile = () => useResource(() => api.profile());
export const useContacts = () => useResource(() => api.contacts());
export const useTags = () => useResource(() => api.tags());
export const useProjects = () => useResource(() => api.projects());
export const useContrib = (w = 52) => useResource(() => api.contrib(w), [w]);
export const usePosts = (params) =>
  useResource(() => api.posts.list(params), [JSON.stringify(params)]);
export const usePost = (id, opts = {}) =>
  useResource(
    () => (id ? api.posts.detail(id, opts) : Promise.resolve(null)),
    // Task 67: previewToken 进 dep 数组，URL 拷贝过来时立刻 refetch。
    [id, opts.previewToken],
  );
export const useNow = () => useResource(() => api.now());
