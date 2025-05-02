// frontend/src/components/ErrorMessage.tsx ---
import React from 'react';
import './ErrorMessage.css';

export interface ErrorMessageProps {
  message: string;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message }) => {
  if (!message) return null;
  return (
    <div className="error-message">
      <p>Error:</p>
      {/* Use pre for better formatting of potential multi-line errors */}
      <pre>{message}</pre>
    </div>
  );
};

export default ErrorMessage;