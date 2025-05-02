// frontend/src/components/GraphDisplay.tsx ---
import React, { useCallback } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Node,
  Edge,
  Connection,
  BackgroundVariant,
  MiniMap,
} from 'reactflow';

import 'reactflow/dist/style.css';

interface GraphDisplayProps {
  initialNodes: Node[];
  initialEdges: Edge[];
  nodes: Node[];
  edges: Edge[];
  height?: string;
}


const GraphDisplay: React.FC<GraphDisplayProps> = ({
  initialNodes,
  initialEdges,
  nodes: currentNodes,
  edges: currentEdges,
  height = '500px',
}) => {
  // State is managed by the parent component (WorkDetailPage),
  // This component primarily renders the passed nodes/edges.
  // We might not need useNodesState/useEdgesState here if the parent fully controls them.
  // Let's keep it for now for internal interactions like onConnect, but rely on props for rendering.

  // const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes); // Use passed nodes directly
  // const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges); // Use passed edges directly
  const [, setEdges, onEdgesChange] = useEdgesState(currentEdges); // Need setEdges for onConnect

  // Reset nodes and edges when initial props change (Potentially remove if parent handles updates)
  // React.useEffect(() => {
  //   setNodes(initialNodes);
  //   setEdges(initialEdges);
  // }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Note: onConnect might need adjustment if nodes/edges state isn't managed here
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds: Edge[]) => addEdge(params, eds)),
    [setEdges]
  );

  const nodeColor = (node: Node) => {
      if (node.id.startsWith('work-')) return '#aaffaa';
      if (node.id.startsWith('repo-')) return '#aaaaff';
      return '#ffaaaa';
  };

  return (
    <div style={{ height: height, border: '1px solid #ddd', borderRadius: '4px' }}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={currentNodes}
          edges={currentEdges}
          // If state is managed by parent, onNodesChange/onEdgesChange might not be needed here
          // onNodesChange={onNodesChange}
          // onEdgesChange={onEdgesChange}
          onConnect={onConnect} // Keep if connections should add edges visually
          fitView
          panOnDrag={true}
          zoomOnScroll={true}
          zoomOnDoubleClick={true}
        >
          <Controls />
          <MiniMap nodeColor={nodeColor} nodeStrokeWidth={3} zoomable pannable />
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
};

export default GraphDisplay;