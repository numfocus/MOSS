import React, { useState } from 'react';
import { INSTITUTION_TYPES_ARRAY } from '../constants/institutionTypes';
import InstitutionType from './InstitutionType';
import './InstitutionTypeFilter.css';

interface InstitutionTypeFilterProps {
  onTypeSelect: (type: string | null) => void;
  selectedType: string | null;
  showAllOption?: boolean;
  className?: string;
}

/**
 * A component for filtering institutions by their type
 * 
 * @param props.onTypeSelect - Callback function when a type is selected
 * @param props.selectedType - Currently selected type
 * @param props.showAllOption - Whether to show an "All Types" option (default: true)
 * @param props.className - Additional CSS classes to apply
 */
const InstitutionTypeFilter: React.FC<InstitutionTypeFilterProps> = ({
  onTypeSelect,
  selectedType,
  showAllOption = true,
  className = ''
}) => {
  return (
    <div className={`institution-type-filter ${className}`}>
      <h4>Filter by Institution Type</h4>
      <div className="institution-type-list">
        {showAllOption && (
          <div 
            className={`institution-type-filter-item ${selectedType === null ? 'selected' : ''}`}
            onClick={() => onTypeSelect(null)}
          >
            <span className="institution-type-icon">🔍</span> All Types
          </div>
        )}
        
        {INSTITUTION_TYPES_ARRAY.map(type => (
          <div 
            key={type.value}
            className={`institution-type-filter-item ${selectedType === type.value ? 'selected' : ''}`}
            onClick={() => onTypeSelect(type.value)}
            title={type.description}
          >
            <InstitutionType 
              type={type.value} 
              showTooltip={false}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default InstitutionTypeFilter; 