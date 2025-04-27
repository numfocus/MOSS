import React, { useEffect, useState } from 'react';
import { useSurreal } from './hooks/useSurreal';
import { DashboardSection } from './components/DashboardSection';
import { Alert, AlertDescription, AlertTitle } from './components/ui/alert';
import { CheckCircleIcon, CircleSlash, Loader2 } from 'lucide-react';

const Dashboard: React.FC = () => {
  const { connectionStatus, error: contextError } = useSurreal();
  const [showAlert, setShowAlert] = useState(false);
  const [alertMessage, setAlertMessage] = useState<string | null>(null);
  const [alertVariant, setAlertVariant] = useState<'default' | 'destructive'>('default');

  useEffect(() => {
    let message: string | null = null;
    let variant: 'default' | 'destructive' = 'default';

    switch (connectionStatus) {
      case 'connecting':
        message = "Connecting to Database...";
        variant = 'default';
        break;
      case 'error':
        message = `Database Connection Error: ${contextError?.message || 'Unknown error'}`;
        variant = 'destructive';
        break;
      case 'disconnected':
        message = "Database Disconnected.";
        variant = 'destructive';
        break;
      case 'connected':
        message = "Database Connected.";
        variant = 'default';
        break;
      default:
        message = null;
    }

    if (message) {
      setAlertMessage(message);
      setAlertVariant(variant);
      setShowAlert(true);
      const timer = setTimeout(() => {
        setShowAlert(false);
      }, 5000); // Hide the alert after 5 seconds
      return () => clearTimeout(timer);
    } else {
      setShowAlert(false);
    }
  }, [connectionStatus, contextError]);

  return (
    <div className="dashboard p-4 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Main Dashboard</h1>

      {showAlert && alertMessage && (
        <Alert variant={alertVariant} className="mb-4">
          {connectionStatus === 'connecting' && <Loader2 className="animate-spin" />}
          {connectionStatus === 'connected' && <CheckCircleIcon />}
          {connectionStatus === 'error' && <CircleSlash />}
          {connectionStatus === 'disconnected' && <CircleSlash />}
          <AlertTitle>{connectionStatus}</AlertTitle>
          <AlertDescription>{alertMessage}</AlertDescription>
        </Alert>
      )}

      {connectionStatus === 'connected' ? (
        <>
          <DashboardSection />
        </>
      ) : (
        <div className="text-center p-5 text-gray-500">
          {connectionStatus !== 'error' ? 'Waiting for database connection...' : 'Database connection error'}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
