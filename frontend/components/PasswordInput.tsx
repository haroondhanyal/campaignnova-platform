'use client';

import { InputHTMLAttributes, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

type Props = InputHTMLAttributes<HTMLInputElement>;

export function PasswordInput(props: Props) {
  const [visible, setVisible] = useState(false);
  return <span className="password-control">
    <input {...props} type={visible ? 'text' : 'password'} />
    <button
      type="button"
      className="password-visibility"
      aria-label={visible ? 'Hide password' : 'Show password'}
      aria-pressed={visible}
      onClick={() => setVisible(value => !value)}
    >{visible ? <EyeOff size={16} /> : <Eye size={16} />}</button>
  </span>;
}
