import React, { useEffect } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface MessageDisplayProps {
  message: string;
  onClose: () => void;
}

const MessageDisplay: React.FC<MessageDisplayProps> = ({ message, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, 3000); // Message will disappear after 3 seconds

    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <Alert className="mb-4">
      <AlertTitle>Message</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
};

export default MessageDisplay;
