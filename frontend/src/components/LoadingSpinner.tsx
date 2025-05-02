// frontend/src/components/LoadingSpinner.tsx ---
import React from 'react';
import './LoadingSpinner.css';

export interface LoadingSpinnerProps {
  message?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message = "Loading..." }) => {
  return (
    <div className="loading-spinner-overlay">
      <div className="loading-spinner"></div>
      {message && <p>{message}</p>}
    </div>
  );
};

export default LoadingSpinner;