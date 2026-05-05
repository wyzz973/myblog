import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PetTemplates from './PetTemplates.jsx';

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    fetchDefaults: vi.fn(),
  },
}));

import { apiPet } from '../../api/pet.js';

const ALL_MODES = [
  'greet', 'idle_monologue', 'recommend_next', 'article_finished',
  'reading_assist', 'code_assist', 'pet_care',
  'summary_react', 'selection_explain', 'selection_qa',
  'free_chat', 'follow_up',
];

beforeEach(() => {
  vi.clearAllMocks();
  apiPet.fetchDefaults.mockResolvedValue({
    templates: Object.fromEntries(ALL_MODES.map((m) => [m, `default ${m}`])),
  });
});

function renderTemplates({ tpl = {}, patch = vi.fn(), onReset = vi.fn() } = {}) {
  const config = { mode_templates: tpl };
  const result = render(
    <PetTemplates config={config} patch={patch} saving={false} onReset={onReset} />,
  );
  return { ...result, patch, onReset };
}

describe('PetTemplates', () => {
  it('renders a fieldset for each of the 12 modes', () => {
    renderTemplates();
    for (const m of ALL_MODES) {
      expect(screen.getByTestId(`mode-${m}`)).toBeInTheDocument();
    }
    // Two visible groups
    expect(screen.getByTestId('mode-group-主动')).toBeInTheDocument();
    expect(screen.getByTestId('mode-group-响应')).toBeInTheDocument();
  });

  it('forwards textarea edits through patch with merged map', () => {
    const { patch } = renderTemplates({ tpl: { greet: 'hi' } });
    fireEvent.change(screen.getByTestId('textarea-pet_care'), {
      target: { value: 'pat the pet' },
    });
    expect(patch).toHaveBeenCalledWith({
      mode_templates: { greet: 'hi', pet_care: 'pat the pet' },
    });
  });

  it('reset-default button writes the per-mode default and is enabled only when dirty', async () => {
    const { patch } = renderTemplates({ tpl: { code_assist: 'custom thing' } });
    // Wait for defaults fetch to populate so the reset button activates.
    await waitFor(() => expect(apiPet.fetchDefaults).toHaveBeenCalled());
    const resetBtn = await waitFor(() => {
      const btn = screen.getByTestId('reset-code_assist');
      expect(btn).not.toBeDisabled();
      return btn;
    });
    fireEvent.click(resetBtn);
    expect(patch).toHaveBeenCalledWith({
      mode_templates: { code_assist: 'default code_assist' },
    });
  });

  it('reset-default disabled when current matches default', async () => {
    renderTemplates({ tpl: { greet: 'default greet' } });
    await waitFor(() => expect(apiPet.fetchDefaults).toHaveBeenCalled());
    const btn = await waitFor(() => screen.getByTestId('reset-greet'));
    expect(btn).toBeDisabled();
  });

  it('全部恢复默认 fires the parent onReset callback', () => {
    const { onReset } = renderTemplates();
    fireEvent.click(screen.getByText('全部恢复默认'));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
