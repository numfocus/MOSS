/**
 * Standard institution types from OpenAlex
 * These are based on the ROR "type" controlled vocabulary
 * @see https://docs.openalex.org/api-entities/institutions/institution-object#type
 */

export interface InstitutionTypeDefinition {
  value: string;
  displayName: string;
  description: string;
  icon: string;
}

export const INSTITUTION_TYPES: Record<string, InstitutionTypeDefinition> = {
  education: {
    value: 'education',
    displayName: 'Education',
    description: 'Universities, colleges, and other educational institutions',
    icon: '🎓'
  },
  healthcare: {
    value: 'healthcare',
    displayName: 'Healthcare',
    description: 'Hospitals, medical centers, and other healthcare facilities',
    icon: '🏥'
  },
  company: {
    value: 'company',
    displayName: 'Company',
    description: 'Commercial entities and businesses',
    icon: '🏢'
  },
  archive: {
    value: 'archive',
    displayName: 'Archive',
    description: 'Libraries, museums, and other archives',
    icon: '📚'
  },
  nonprofit: {
    value: 'nonprofit',
    displayName: 'Nonprofit',
    description: 'Non-profit organizations and NGOs',
    icon: '🤝'
  },
  government: {
    value: 'government',
    displayName: 'Government',
    description: 'Government agencies and public bodies',
    icon: '🏛️'
  },
  facility: {
    value: 'facility',
    displayName: 'Facility',
    description: 'Research facilities, laboratories, and specialized centers',
    icon: '🔬'
  },
  other: {
    value: 'other',
    displayName: 'Other',
    description: 'Organizations that don\'t fit in other categories',
    icon: '📋'
  }
};

/**
 * Array of institution types for dropdown menus, etc.
 */
export const INSTITUTION_TYPES_ARRAY = Object.values(INSTITUTION_TYPES);

/**
 * Get a formatted display name for an institution type
 * @param type The raw institution type string
 * @returns Properly formatted display name or the original string if not found
 */
export const getInstitutionTypeDisplayName = (type: string | null | undefined): string => {
  if (!type) return 'Unknown';
  
  const typeKey = type.toLowerCase();
  return INSTITUTION_TYPES[typeKey]?.displayName || 
    type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
};

/**
 * Get the icon for an institution type
 * @param type The raw institution type string
 * @returns The icon for the institution type, or a question mark for unknown types
 */
export const getInstitutionTypeIcon = (type: string | null | undefined): string => {
  if (!type) return '❓';
  
  const typeKey = type.toLowerCase();
  return INSTITUTION_TYPES[typeKey]?.icon || '❓';
};

export default INSTITUTION_TYPES; 