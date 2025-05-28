import React from 'react';
import { 
  getInstitutionTypeDisplayName, 
  getInstitutionTypeIcon,
  INSTITUTION_TYPES
} from '../constants/institutionTypes';

interface InstitutionTypeProps {
  type: string | null | undefined;
  showIcon?: boolean;
  className?: string;
  showTooltip?: boolean;
}

/**
 * A component for displaying institution types with consistent formatting and styling
 * based on the OpenAlex institution type vocabulary.
 * 
 * @param props.type - The institution type (from OpenAlex)
 * @param props.showIcon - Whether to show an icon (default: true)
 * @param props.className - Additional CSS classes to apply
 * @param props.showTooltip - Whether to show a tooltip with the description (default: true)
 */
const InstitutionType: React.FC<InstitutionTypeProps> = ({ 
  type, 
  showIcon = true,
  className = '',
  showTooltip = true
}) => {
  if (!type) return <span className="text-muted">N/A</span>;
  
  // Get display name and icon from constants
  const displayName = getInstitutionTypeDisplayName(type);
  const icon = getInstitutionTypeIcon(type);
  
  // Apply specific styling based on institution type
  const typeKey = type.toLowerCase();
  const baseClassName = `institution-type institution-type-${typeKey in INSTITUTION_TYPES ? typeKey : 'unknown'}`;
  
  // Get description for tooltip
  const description = typeKey in INSTITUTION_TYPES ? 
    INSTITUTION_TYPES[typeKey].description : 
    'Unknown institution type';
  
  return (
    <span 
      className={`${baseClassName} ${className}`}
      title={showTooltip ? description : undefined}
    >
      {showIcon && <span className="institution-type-icon">{icon}</span>}
      {displayName}
    </span>
  );
};

export default InstitutionType; 