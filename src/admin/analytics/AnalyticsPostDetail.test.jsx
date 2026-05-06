// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AnalyticsPostDetail from './AnalyticsPostDetail.jsx';

vi.mock('../../api/analytics.js', () => ({
  apiAnalytics: { postTimeseries: vi.fn() },
}));
import { apiAnalytics } from '../../api/analytics.js';

const SAMPLE = {
  post_id: 'p25c-demo',
  title: 'Demo Post',
  total: 42,
  timeseries: [
    { date: '2026-04-29', hits: 0 },
    { date: '2026-04-30', hits: 5 },
    { date: '2026-05-01', hits: 7 },
    { date: '2026-05-02', hits: 12 },
    { date: '2026-05-03', hits: 8 },
    { date: '2026-05-04', hits: 6 },
    { date: '2026-05-05', hits: 4 },
  ],
};

function renderWithRouter(initialUrl = '/admin/analytics/posts/p25c-demo?range=7d') {
  return render(
    <MemoryRouter initialEntries={[initialUrl]}>
      <Routes>
        <Route path="/admin/analytics/posts/:postId" element={<AnalyticsPostDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  apiAnalytics.postTimeseries.mockResolvedValue(SAMPLE);
});
afterEach(() => {
  vi.clearAllMocks();
});

describe('AnalyticsPostDetail', () => {
  it('fetches the timeseries with the active range and renders title + total', async () => {
    renderWithRouter();
    await waitFor(() => screen.getByTestId('post-detail-total'));
    expect(apiAnalytics.postTimeseries).toHaveBeenCalledWith('p25c-demo', '7d');
    expect(screen.getByText('Demo Post', { exact: false })).toBeInTheDocument();
    expect(screen.getByTestId('post-detail-total').textContent).toBe('42');
  });

  it('renders one bar per timeseries day with a tooltip <title>', async () => {
    renderWithRouter();
    await waitFor(() => screen.getByTestId('post-detail-total'));
    for (const pt of SAMPLE.timeseries) {
      const bar = screen.getByTestId(`bar-${pt.date}`);
      expect(bar).toBeInTheDocument();
      // The <title> child is the tooltip — assert it carries date + hits.
      expect(bar.querySelector('title').textContent).toBe(`${pt.date}: ${pt.hits}`);
    }
  });

  it('clicking a range chip refetches with the new range', async () => {
    renderWithRouter();
    await waitFor(() => screen.getByTestId('post-detail-total'));
    fireEvent.click(screen.getByTestId('range-30d'));
    await waitFor(() =>
      expect(apiAnalytics.postTimeseries).toHaveBeenLastCalledWith('p25c-demo', '30d'),
    );
  });

  it('surfaces 404 in the error region', async () => {
    const err = new Error('404 post not found');
    err.status = 404;
    err.detail = 'post not found';
    apiAnalytics.postTimeseries.mockRejectedValue(err);
    renderWithRouter();
    await waitFor(() => screen.getByTestId('post-detail-error'));
    expect(screen.getByTestId('post-detail-error').textContent.toLowerCase())
      .toContain('post not found');
  });

  it('uses 30d default when ?range= is missing or invalid', async () => {
    renderWithRouter('/admin/analytics/posts/p25c-demo');
    await waitFor(() => screen.getByTestId('post-detail-total'));
    expect(apiAnalytics.postTimeseries).toHaveBeenCalledWith('p25c-demo', '30d');
  });

  // Task 25b-csv-drilldown
  it('passes range:from..to through to the API and shows the custom-range label', async () => {
    renderWithRouter('/admin/analytics/posts/p25c-demo?range=range:2026-04-01..2026-04-10');
    await waitFor(() => screen.getByTestId('post-detail-total'));
    expect(apiAnalytics.postTimeseries).toHaveBeenCalledWith(
      'p25c-demo', 'range:2026-04-01..2026-04-10',
    );
    expect(screen.getByTestId('range-custom-label').textContent).toContain('2026-04-01');
    expect(screen.getByTestId('range-custom-label').textContent).toContain('2026-04-10');
  });

  it('passes since:YYYY-MM-DD through to the API', async () => {
    renderWithRouter('/admin/analytics/posts/p25c-demo?range=since:2026-04-21');
    await waitFor(() => screen.getByTestId('post-detail-total'));
    expect(apiAnalytics.postTimeseries).toHaveBeenCalledWith(
      'p25c-demo', 'since:2026-04-21',
    );
    expect(screen.getByTestId('range-custom-label').textContent).toContain('自 2026-04-21');
  });
});
