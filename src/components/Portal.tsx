import { ReactNode, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

interface PortalProps {
  children: ReactNode;
  containerId: string;
}

const Portal: React.FC<PortalProps> = ({ children, containerId }) => {
  const containerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const container = document.getElementById(containerId);
    if (container) {
      containerRef.current = container;
    }
  }, [containerId]);

  if (!containerRef.current) {
    return null;
  }

  return createPortal(children, containerRef.current);
};

export default Portal;
