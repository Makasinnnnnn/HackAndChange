import * as Select from '@radix-ui/react-select';
import {Check, ChevronDown, ChevronUp} from 'lucide-react';
import {useId, useState} from 'react';

type Choice = {value: string; label: string};

type ChoiceFieldProps = {
  label: string;
  value: string;
  options: Choice[];
  emptyLabel: string;
  clearable?: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
};

export function ChoiceField({label, value, options, emptyLabel, clearable, disabled, onChange}: ChoiceFieldProps) {
  const labelId = useId();
  const [pointerOpen, setPointerOpen] = useState(false);
  // Prefix values so the optional empty choice is a valid Radix item.
  const choices = clearable ? [{value: '', label: emptyLabel}, ...options] : options;
  const selected = choices.some(choice => choice.value === value) ? ':' + value : '';

  return <div className="choice-field">
    <span id={labelId} className={clearable ? 'choice-label' : 'sr-only'}>{label}</span>
    <Select.Root value={selected} disabled={disabled} onValueChange={next => onChange(next.slice(1))}>
      <Select.Trigger
        className="choice-trigger"
        aria-labelledby={labelId}
        onPointerDown={() => setPointerOpen(true)}
        onKeyDown={() => setPointerOpen(false)}
      >
        <span className="choice-value"><Select.Value placeholder={emptyLabel}/></span>
        <Select.Icon className="choice-chevron" asChild><ChevronDown size={18}/></Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content className="choice-menu" data-pointer={pointerOpen} position="popper" sideOffset={6} collisionPadding={12}>
          <Select.ScrollUpButton className="choice-scroll"><ChevronUp size={16}/></Select.ScrollUpButton>
          <Select.Viewport className="choice-options">
            {choices.map(option => <Select.Item className="choice-option" key={option.value} value={':' + option.value}>
              <Select.ItemText>{option.label}</Select.ItemText>
              <Select.ItemIndicator className="choice-check"><Check size={17}/></Select.ItemIndicator>
            </Select.Item>)}
          </Select.Viewport>
          <Select.ScrollDownButton className="choice-scroll"><ChevronDown size={16}/></Select.ScrollDownButton>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  </div>;
}
