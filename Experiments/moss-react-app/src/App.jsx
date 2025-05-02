import React, { useEffect, useRef, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import SpriteText from 'three-spritetext';
import neo4j from 'neo4j-driver';

// Predefined queries for the dropdown
const premadeQueries = [
  {
    label: 'Projects cited by Papers addressing Climate Action',
    query: `
      MATCH (p:Project)<-[:CITES]-(pa:Paper)-[:ADDRESSES]->(s:SDG)
      WHERE s.Name = 'Climate action'
      RETURN { id: id(p), label:head(labels(p)), caption:p.Name } as p, 
             { id: id(pa), label:head(labels(pa)), caption:pa.Name } as pa, 
             { id: id(s), label:head(labels(s)), caption:s.Name } as s
      LIMIT $limit
    `
  },
  {
    label: 'Projects cited by Papers addressing No Poverty',
    query: `
      MATCH (p:Project)<-[:CITES]-(pa:Paper)-[:ADDRESSES]->(s:SDG)
      WHERE s.Name = 'No poverty'
      RETURN { id: id(p), label:head(labels(p)), caption:p.Name } as p, 
             { id: id(pa), label:head(labels(pa)), caption:pa.Name } as pa, 
             { id: id(s), label:head(labels(s)), caption:s.Name } as s
      LIMIT $limit
    `
  }
  // Add more premade queries as needed
];

// Function to execute a query and return nodes and links
async function ExecuteQuery(session, query, includeProjects, existingNodes, existingLinks) {
  const result = await session.run(query, { limit: neo4j.int(5000) });

  // Initialize nodes and links with existing data
  const nodes = { ...existingNodes };
  const links = [...existingLinks];

  result.records.forEach(r => {
    const project = r.get('p');
    const paper = r.get('pa');
    const sdg = r.get('s');

    // Process paper and SDG nodes
    [paper, sdg].forEach(node => {
      node.id = node.id.toNumber();
      if (!nodes[node.id]) {
        nodes[node.id] = { ...node, connections: 0 };
      }
      nodes[node.id].connections++;
    });

    // Process project nodes if includeProjects is true
    if (includeProjects) {
      project.id = project.id.toNumber();
      if (!nodes[project.id]) {
        nodes[project.id] = { ...project, connections: 0 };
      }
      nodes[project.id].connections++;
      links.push({ source: paper.id, target: project.id });
    }

    // Always add link between paper and SDG
    links.push({ source: paper.id, target: sdg.id });
  });

  return { nodes, links };
}

const GraphVisualization = () => {
  const [graphData, setGraphData] = useState({ nodes: {}, links: [] }); // State to store graph data
  const [customQuery, setCustomQuery] = useState(""); // State to store custom query
  const [selectedQuery, setSelectedQuery] = useState(premadeQueries[0].query); // State to store selected query from dropdown
  const [showProjects, setShowProjects] = useState(true); // State to toggle showing projects
  const driverRef = useRef(null); // Ref to store Neo4j driver instance
  const graphRef = useRef(); // Ref to store graph instance

  // Initialize Neo4j driver only once
  useEffect(() => {
    if (!driverRef.current) {
      driverRef.current = neo4j.driver("bolt://localhost:7689", neo4j.auth.basic("neo4j", "mossmossmoss"));
    }
  }, []); // Empty dependency array ensures this effect runs only once

  // Function to load data and update graph
  const loadData = async (query, includeProjects) => {
    const session = driverRef.current.session({ database: "neo4j" });
    const start = new Date();

    try {
      const { nodes, links } = await ExecuteQuery(session, query, includeProjects, graphData.nodes, graphData.links);

      // Sort nodes by connection count and show labels for the top N nodes
      const nodeArray = Object.values(nodes);
      nodeArray.sort((a, b) => b.connections - a.connections);
      const topN = 100; // Set the number of top nodes to show labels for
      nodeArray.slice(0, topN).forEach(node => node.showLabel = true);

      setGraphData({
        nodes,
        links
      });

      console.log(links.length + " links loaded in " + (new Date() - start) + " ms.");
    } catch (error) {
      console.error(error);
    } finally {
      session.close();
    }
  };

  // Handler to submit query
  const handleQuerySubmit = () => {
    loadData(customQuery || selectedQuery, showProjects);
  };

  // Handler to toggle showing projects
  const handleToggleProjects = () => {
    setShowProjects(!showProjects);
    loadData(customQuery || selectedQuery, !showProjects); // Reload data with the new toggle state
  };

  // Handler to clear all nodes
  const handleClearAll = () => {
    setGraphData({ nodes: {}, links: [] });
  };

  return (
    <div>
      <div>
        {/* Dropdown to select predefined queries */}
        <select onChange={(e) => setSelectedQuery(e.target.value)}>
          {premadeQueries.map((q, index) => (
            <option key={index} value={q.query}>
              {q.label}
            </option>
          ))}
        </select>
        {/* Textarea for custom query input */}
        <textarea 
          value={customQuery} 
          onChange={(e) => setCustomQuery(e.target.value)} 
          placeholder="Enter custom query (optional)" 
        />
        {/* Button to submit query */}
        <button onClick={handleQuerySubmit}>Submit</button>
        {/* Button to toggle showing projects */}
        <button onClick={handleToggleProjects}>
          {showProjects ? 'Hide' : 'Show'} Projects
        </button>
        {/* Button to clear all nodes */}
        <button onClick={handleClearAll}>Clear All Nodes</button>
      </div>
      <ForceGraph3D
        ref={graphRef}
        graphData={{ nodes: Object.values(graphData.nodes), links: graphData.links }} // Convert nodes object to array
        nodeAutoColorBy="label"
        nodeLabel={node => `${node.label}: ${node.caption}`}
        nodeThreeObject={node => {
          if (node.showLabel) {
            const sprite = new SpriteText(`${node.label}: ${node.caption}`);
            sprite.material.depthWrite = false; // Make sprite background transparent
            sprite.color = node.color;
            sprite.textHeight = 8;
            return sprite;
          }
          return null;
        }}
        onNodeHover={node => {
          if (graphRef.current) {
            graphRef.current.renderer().domElement.style.cursor = node ? 'pointer' : null;
          }
        }}
      />
    </div>
  );
};

const App = () => (
  <div>
    <GraphVisualization />
  </div>
);

export default App;
