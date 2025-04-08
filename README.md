# Map of Open Source Science (MOSS)

MOSS is a project of [OSSci](https://www.opensource.science/), an initiative of [NumFOCUS](https://numfocus.org/).

## Overview

The Map of Open Source Science (MOSS) is a visualization tool that maps the intersection between open source software and scientific research. It creates a network graph that shows relationships between research papers, software repositories, authors, and other entities in the open science ecosystem. This visualization helps researchers, funders, and policymakers understand the complex relationships and dependencies within the scientific software landscape.

> The current version of MOSS is a proof of concept and is continuously being improved.

## Architecture

MOSS consists of several key components:

- **Data Collection Scripts**: Python scripts for collecting data from services like [ecosyst.ms](https://papers.ecosyste.ms/) API
- **Neo4j Graph Database**: Stores the relationship data between papers, repositories, authors, etc.
- **React Frontend**: Provides an interactive visualization of the graph data
- **API Layer**: Connects the frontend to the backend database

## Technology Stack

- **Backend**: Python 3.11+, Neo4j (graph database)
- **Frontend**: React, Vite
- **Data Processing**: Custom Python scripts
- **Deployment**: Docker support for Neo4j
- **Documentation**: MkDocs

## Getting Started

For detailed setup instructions, see [the setup guide](./scripts/README.md) which includes:

1. Installing and configuring Neo4j
2. Collecting data using the provided scripts
3. Importing data into the graph database
4. Visualizing the data with Neo4j Bloom

### Quick Start with Docker

If you prefer to use Docker for Neo4j:

1. Navigate to the `neo4j-docker` directory
2. Create an `.env` file based on the provided example
3. Run `docker compose up -d`
4. Follow the data collection and import instructions in the [setup guide](./scripts/README.md)

### Frontend Development

To work on the React frontend:

1. Navigate to the `moss-react-app` directory
2. Install dependencies with `npm install`
3. Start the development server with `npm run dev`

## Features

- **Interactive Graph Visualization**: Explore connections between papers, software, and authors
- **Search and Filter**: Find specific entities and their relationships
- **Data Collection Tools**: Scripts to gather data from various sources
- **API Integration**: Connect with ecosyst.ms and other scientific metadata services

## Data Sources

MOSS collects data from multiple sources including:

- [ecosyst.ms](https://papers.ecosyste.ms/): For paper metadata and citations
- GitHub: For repository information and relationships
- Additional scientific data repositories (expanding)

## Goal

We aim to create a comprehensive, interactive visualization of the open source scientific ecosystem that surpasses our earlier prototype:
- [Previous Kumu visualization](https://embed.kumu.io/6cbeee6faebd8cc57590da7b83c4d457#default)
- [Demo video](https://www.youtube.com/watch?v=jZyLSRCba_M)

The goal is to make the relationships between scientific software and research more transparent, helping the community understand the impact and dependencies of open source software in scientific research.

## Contributing

We welcome contributions from the community! We are using the [fork and pull](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/getting-started/about-collaborative-development-models#fork-and-pull-model) collaborative development model.

To contribute:
1. Check the [open issues](../../issues) for tasks that need attention
2. Fork the repository
3. Create a branch for your changes
4. Submit a pull request

See the [CONTRIBUTING.md](./CONTRIBUTING.md) file for more detailed guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.
