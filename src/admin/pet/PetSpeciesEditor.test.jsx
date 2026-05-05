import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PetSpeciesEditor from './PetSpeciesEditor.jsx';

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

  it('renders frame count badge', async () => {
    render(<PetSpeciesEditor />);
    await waitFor(() => screen.getByTestId('species-row-duck'));
    expect(screen.getByTestId('species-row-duck').textContent).toContain('3 frames');
  });
});
