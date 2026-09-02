import React from 'react';

export interface BadgeProps {
  variant?: 'blue' | 'green' | 'amber' | 'red' | 'gray' | 'purple';
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'gray',
  children,
  className = '',
  onClick,
}) => {
  const variantClass = `badge-${variant}`;
  return (
    <span
      className={`badge ${variantClass} ${className} ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      {children}
    </span>
  );
};
