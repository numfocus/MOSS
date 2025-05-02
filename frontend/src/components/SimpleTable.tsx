// frontend/src/components/SimpleTable.tsx ---

import React from 'react';
import { Link } from 'react-router-dom';
import './SimpleTable.css';

export interface SimpleTableProps {
  headers: string[];
  data: Record<string, any>[];
}

const getLinkForIdColumn = (header: string, value: any): React.ReactNode | null => {
  if (value === null || value === undefined || String(value).trim() === '') {
    return null;
  }

  const idValue = String(value);

  if (header.toLowerCase().endsWith('repository_id') || header.toLowerCase() === 'repoid') {
    return <Link to={`/repositories/${idValue}`}>{idValue}</Link>;
  } else if (header.toLowerCase().endsWith('work_id') || header.toLowerCase() === 'workid') {
    return <Link to={`/works/${idValue}`}>{idValue}</Link>;
  } else if (header.toLowerCase().endsWith('person_id') || header.toLowerCase() === 'personid') {
    return <Link to={`/persons/${idValue}`}>{idValue}</Link>;
  } else if (header.toLowerCase().endsWith('institution_id') || header.toLowerCase() === 'institutionid') {
    return <Link to={`/institutions/${idValue}`}>{idValue}</Link>;
  } else if (header.toLowerCase().endsWith('contributor_id') || header.toLowerCase() === 'contributorid') {
    return idValue;
  }
  // Add more mappings as needed (e.g., owner_id, session_id etc.)

  return null;
};


const SimpleTable: React.FC<SimpleTableProps> = ({ headers, data }) => {
  if (!data || data.length === 0) {
    return <p>No data available for table display.</p>;
  }

  if (!headers || headers.length === 0) {
      console.warn("SimpleTable received empty or missing headers prop.");
      if (data[0] && typeof data[0] === 'object'){
          headers = Object.keys(data[0]);
      } else {
          return <p>Table headers are missing.</p>;
      }
  }


  return (
    <div className="simple-table-container">
      <table className="simple-table">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((header) => {
                const value = row[header];
                let displayValue: React.ReactNode = '';

                const idLink = getLinkForIdColumn(header, value);
                if (idLink !== null) {
                    displayValue = idLink;
                } else if (value === null || value === undefined) {
                    displayValue = '';
                } else if (React.isValidElement(value)) {
                    displayValue = value;
                } else if (typeof value === 'object') {
                    try {
                         displayValue = JSON.stringify(value, null, 2);
                    } catch (stringifyError){
                        displayValue = '[Invalid Object]';
                    }
                 } else {
                    displayValue = String(value);
                 }

                const cellContent = (typeof displayValue === 'string' && (displayValue.startsWith('{') || displayValue.startsWith('[')))
                    ? <pre><code>{displayValue}</code></pre>
                    : displayValue;

                return <td key={`${rowIndex}-${header}`}>{cellContent}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default SimpleTable;