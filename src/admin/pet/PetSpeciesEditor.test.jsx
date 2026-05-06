import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PetSpeciesEditor, { frameLayoutHint } from './PetSpeciesEditor.jsx';

vi.mock('../../api/petSpecies.js', () => ({
  apiPetSpecies: {
    list: vi.fn(),
    create: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));
import { apiPetSpecies } from '../../api/petSpecies.js';

const SAMPLE = [
  {
    id: 'duck', name: 'Duck', rarity: 'common', color: '#f5d44c',
    trait_zh: 'rubber debugger', personality_zh: 'cheerful', description_zh: 'a duck',
    frames: [['a'], ['b'], ['c']], behavior: {}, stats: {},
    visible: true, sort_order: 0,
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z',
  },
  {
    id: 'dragon', name: 'Dragon', rarity: 'legendary', color: '#ff7a5c',
    trait_zh: '', personality_zh: '', description_zh: '',
    frames: [['x'], ['y'], ['z']], behavior: {}, stats: {},
    visible: false, sort_order: 18,
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z',
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  apiPetSpecies.list.mockResolvedValue(SAMPLE);
  // Confirm dialog: default to "yes" so delete/create flows progress.
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

describe('PetSpeciesEditor', () => {
  it('groups rows by rarity and renders one fieldset per row', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    expect(screen.getByTestId('species-group-common')).toBeInTheDocument();
    expect(screen.getByTestId('species-group-legendary')).toBeInTheDocument();
    expect(screen.getByTestId('species-row-duck')).toBeInTheDocument();
    expect(screen.getByTestId('species-row-dragon')).toBeInTheDocument();
  });

  it('marks a row dirty when an input changes and enables save', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));

    const saveBtn = screen.getByTestId('species-save-duck');
    expect(saveBtn).toBeDisabled();

    fireEvent.change(screen.getByTestId('species-name-duck'), {
      target: { value: 'Ducky' },
    });
    expect(screen.getByTestId('species-row-duck').getAttribute('data-dirty')).toBe('true');
    expect(saveBtn).not.toBeDisabled();
  });

  it('PATCH on save sends only the changed fields and refreshes the row', async () => {
    apiPetSpecies.patch.mockResolvedValue({
      ...SAMPLE[0], name: 'Ducky',
      updated_at: '2026-05-06T00:00:00Z',
    });
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));

    fireEvent.change(screen.getByTestId('species-name-duck'), {
      target: { value: 'Ducky' },
    });
    fireEvent.click(screen.getByTestId('species-save-duck'));

    await waitFor(() => expect(apiPetSpecies.patch).toHaveBeenCalledTimes(1));
    expect(apiPetSpecies.patch).toHaveBeenCalledWith('duck', { name: 'Ducky' });

    // After save the row is no longer dirty and shows the new name.
    await waitFor(() => {
      expect(screen.getByTestId('species-row-duck').getAttribute('data-dirty')).toBe('false');
    });
    expect(screen.getByTestId('species-name-duck').value).toBe('Ducky');
  });

  it('surfaces 409 from delete (default-pet conflict)', async () => {
    const err = new Error('409');
    err.status = 409;
    err.detail = "species 'duck' is the site's default pet";
    apiPetSpecies.delete.mockRejectedValue(err);
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));

    fireEvent.click(screen.getByTestId('species-delete-duck'));
    await waitFor(() => screen.getByTestId('species-error'));
    expect(screen.getByTestId('species-error').textContent.toLowerCase()).toContain('default pet');
    // Row must still be present.
    expect(screen.getByTestId('species-row-duck')).toBeInTheDocument();
  });

  it('add-new flow posts the draft and prepends the result', async () => {
    apiPetSpecies.create.mockResolvedValue({
      id: 'kraken', name: 'Kraken', rarity: 'epic', color: '#123456',
      trait_zh: '', personality_zh: '', description_zh: '',
      frames: [], behavior: {}, stats: {},
      visible: true, sort_order: 999,
      created_at: '2026-05-06T00:00:00Z', updated_at: '2026-05-06T00:00:00Z',
    });
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));

    fireEvent.click(screen.getByTestId('species-add-toggle'));
    fireEvent.change(screen.getByTestId('species-new-id'), { target: { value: 'kraken' } });
    fireEvent.change(screen.getByTestId('species-new-name'), { target: { value: 'Kraken' } });
    fireEvent.change(screen.getByTestId('species-new-rarity'), { target: { value: 'epic' } });
    fireEvent.click(screen.getByTestId('species-new-create'));

    await waitFor(() => expect(apiPetSpecies.create).toHaveBeenCalledTimes(1));
    expect(apiPetSpecies.create).toHaveBeenCalledWith(expect.objectContaining({
      id: 'kraken', name: 'Kraken', rarity: 'epic',
    }));
    await waitFor(() => screen.getByTestId('species-row-kraken'));
  });

  it('renders frame count on the toggle button', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    expect(screen.getByTestId('species-frames-toggle-duck').textContent)
      .toContain('编辑帧 (3)');
  });
});

// --- Task 21f: frame editor ---

describe('frameLayoutHint', () => {
  const SPEC = ['            ', '   /\\__/\\   ', '  ( {E}  {E} )  ', '  (  ω   )  ', '  (")__(")  '];
  it('returns null for the canonical 5×12 shape', () => {
    expect(frameLayoutHint(SPEC)).toBeNull();
  });
  it('flags wrong row count', () => {
    expect(frameLayoutHint(SPEC.slice(0, 3))).toContain('3 行');
  });
  it('flags wrong column width per row', () => {
    const off = [...SPEC];
    off[0] = '            x'; // 13 chars
    const hint = frameLayoutHint(off);
    expect(hint).toContain('第 1 行 13');
  });
  it('counts {E} as a single character (X) for width', () => {
    expect(frameLayoutHint(SPEC)).toBeNull();
    // SPEC line 2 is '  ( {E}  {E} )  ' which is 12 chars after E→X.
    expect(SPEC[2].replace(/\{E\}/g, 'X').length).toBe(12);
  });
  it('returns null for non-array inputs (defensive)', () => {
    expect(frameLayoutHint(null)).toBeNull();
    expect(frameLayoutHint(undefined)).toBeNull();
  });
});

describe('PetSpeciesEditor — frames panel', () => {
  it('toggle expands the frames panel and shows three textareas', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    expect(screen.queryByTestId('species-frames-panel-duck')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('species-frames-toggle-duck'));
    expect(screen.getByTestId('species-frames-panel-duck')).toBeInTheDocument();
    expect(screen.getByTestId('species-frame-duck-0')).toBeInTheDocument();
    expect(screen.getByTestId('species-frame-duck-1')).toBeInTheDocument();
    expect(screen.getByTestId('species-frame-duck-2')).toBeInTheDocument();
  });

  it('editing a frame updates the dirty flag and shows the layout hint', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    fireEvent.click(screen.getByTestId('species-frames-toggle-duck'));

    const fa = screen.getByTestId('species-frame-duck-0');
    fireEvent.change(fa, { target: { value: 'short' } });
    expect(screen.getByTestId('species-row-duck').getAttribute('data-dirty')).toBe('true');
    // 1 row != 5 expected → hint surfaces row-count mismatch
    expect(screen.getByTestId('species-frame-hint-duck-0').textContent).toContain('1 行');
  });

  it('save sends the updated frames array via PATCH', async () => {
    apiPetSpecies.patch.mockResolvedValue({
      ...SAMPLE[0],
      frames: [['line1', 'line2'], ['b'], ['c']],
    });
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    fireEvent.click(screen.getByTestId('species-frames-toggle-duck'));

    fireEvent.change(screen.getByTestId('species-frame-duck-0'), {
      target: { value: 'line1\nline2' },
    });
    fireEvent.click(screen.getByTestId('species-save-duck'));
    await waitFor(() => expect(apiPetSpecies.patch).toHaveBeenCalledTimes(1));
    const [, body] = apiPetSpecies.patch.mock.calls[0];
    expect(body.frames).toBeInstanceOf(Array);
    expect(body.frames[0]).toEqual(['line1', 'line2']);
    // Other frames preserved as-is from the source row.
    expect(body.frames[1]).toEqual(['b']);
    expect(body.frames[2]).toEqual(['c']);
  });

  it('toggle button label flips to 收起帧 while panel is open', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    const btn = screen.getByTestId('species-frames-toggle-duck');
    expect(btn.textContent).toContain('编辑帧');
    fireEvent.click(btn);
    expect(btn.textContent).toContain('收起帧');
    fireEvent.click(btn);
    expect(btn.textContent).toContain('编辑帧');
  });
});
