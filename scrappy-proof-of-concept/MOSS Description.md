# **Map of Open Source Science (MOSS): Connecting Research Software and Scholarly Knowledge**

## **What is MOSS?**

The Map of Open Source Science (MOSS) is a comprehensive database and platform that reveals the hidden connections between research software and academic scholarship. It creates a rich, interconnected map of the research ecosystem by gathering data about software repositories, academic papers, researchers, and institutions, then discovering and visualizing the relationships between them.

MOSS helps answer critical questions that were previously difficult to address:

* How is my research software being used across different scientific fields?  
* Which institutions are contributing to open source scientific tools?  
* Who are the key contributors in specific research software domains?  
* What's the health and sustainability of research software projects?  
* How effectively is grant funding translating into usable research tools?  

## **Why MOSS Matters**

Research software has become essential to scientific discovery, yet we lack good tools to understand how software and traditional research outputs connect. MOSS bridges this gap by creating a unified view of both worlds:

* **For Researchers**: Discover how your software is used in publications, find potential collaborators, and demonstrate the impact of your code.

* **For Institutions**: Map your organization's software contributions, identify external collaborations, and showcase your influence in the open science ecosystem.

* **For Funding Agencies**: Track the outputs and impact of funded software projects, evaluate return on investment, and inform future funding decisions.

* **For Research Software Engineers**: Find health metrics for repositories, identify potential contributors, and improve project sustainability.

## **How MOSS Works**

MOSS operates through three distinct core operations:

### **Key Operations**

1. **Discovery & Ingestion**: Finding and adding data to the system with no filtering applied
2. **Surfacing**: Finding and filtering specific entities from the collected data  
3. **Analysis**: Extracting meaningful insights from surfaced entities

### **1\. Discovery & Ingestion Mode: Finding and Adding Comprehensive Data**

In this mode, MOSS gathers information from multiple sources to build its knowledge graph, always casting a wide net to ensure complete data collection:

* **Direct Repository Discovery & Ingestion**: Add GitHub repositories directly by URL or in bulk  
* **Keyword-Based Discovery & Ingestion**: Find and collect all repositories based on research topics or terms  
* **Domain-Based Discovery & Ingestion**: Find and collect all repositories associated with specific institutional domains  
* **DOI-Based Discovery & Ingestion**: Add academic papers and connect them to related software

During discovery & ingestion, MOSS extracts all available metadata without applying filtering, ensuring maximum data collection. Each piece of information is preserved with its source and discovery method, creating a complete provenance trail.

### **2\. Surfacing Mode: Finding Relevant Connections from Existing Data**

This mode helps you explore and identify relevant entities from the ingested data based on various criteria:

* **Institutional Repository Surfacing**: Surface all software associated with an institution using multiple confidence signals  
* **Relationship Surfacing**: Find repositories connected through citations, contributors, or code dependencies  
* **Custom Filtering Algorithms**: Build complex filters to surface repositories matching specific criteria

When a surfacing operation detects that requested data might not exist in the database, MOSS offers a seamless transition to the discovery & ingestion mode to collect the missing data.

MOSS uses customizable Association Confidence Filters (ACFs) during surfacing to accurately surface the user requested data. For example, a user can define how they want to determine the association of a repository to an institution, write that definition in an ACF, and apply that ACF to the MOSS database.

### **3\. Analysis Mode: Extracting Insights**

Once you've surfaced relevant entities, you can apply custom or predefined (from the MOSS community) analysis algorithms. For example:

* **Research Impact Analysis**: Analyze citation patterns, research topic distribution, and knowledge flow across disciplines  
* **Contributor Analysis**: Identify core contributors, track institutional participation, and map collaboration networks  
* **Usage & Engagement Analysis**: Measure community responsiveness, engagement trends, and passive user identification  
* **Institutional Analysis**: Evaluate institutional software portfolios and cross-institutional collaboration  
* **Repository Health Assessment**: Measure code health, documentation quality, community vitality, and sustainability

Each analysis type offers visualizations, metrics, and comparison capabilities to help understand patterns and trends. 

Critical to MOSS is the concept of open algorithms. For example, users can create their own definitions of impact, write those definitions into analysis algorithms, and apply those algorithms over the MOSS database. The community can upload their algorithms to the MOSS Aglorithm Index, where users can select them to run over their surfaced data.

### **4\. Management Mode: Customizing Tools**

MOSS provides basic customization through its management capabilities:

* **Algorithm Management**: Configure and select from available algorithms for confidence filtering (used in surfacing), impact measurements, and health assessments  
* **Data Management**: Control data quality, freshness, and consistency  
* **Integration Management**: Connect MOSS with external systems like institutional repositories or bibliography managers  
* **User Administration**: Manage access controls and user preferences

The system includes proof-of-concept implementations for each algorithm type, with the ability to extend functionality through the codebase in future versions.

## **Real-World Scenarios**

### **For a University Research Office**

**Scenario**: A university wants to understand their institution's contributions to open source science.

**With MOSS**: They first run comprehensive discovery & ingestion operations using their institutional domains to collect all potentially relevant data. Then, they surface repositories created by their researchers and also identify contributions their researchers make to external projects. Finally, they analyze the impact of their software across different disciplines, showcase interdisciplinary collaboration, and demonstrate research impact beyond publications.

### **For an Individual Researcher**

**Scenario**: A researcher wants to understand the impact of their software tool and find potential collaborators.

**With MOSS**: After ensuring their software is discovered and ingested, they can surface all relevant connections to their work. They can track citations to their software across publications, see which research fields are using their tool, identify institutions adopting their software, and discover similar projects for potential collaboration.

### **For a Funding Agency**

**Scenario**: A funding agency wants to assess the outcomes of their software development grants.

**With MOSS**: They first ensure all grant-related software is discovered and ingested, then surface all repositories associated with specific grants. Finally, they can analyze the outcomes by measuring citation and usage metrics, evaluating sustainability and health scores, and calculating impact per dollar invested across different funding programs.

## **The MOSS Difference**

Unlike traditional research information systems or repository analytics, MOSS offers:

1. **Unified Knowledge Graph**: Connects software and scholarly outputs in a single integrated view

2. **Comprehensive Discovery & Ingestion Philosophy**: Collects all potentially relevant data without filtering during discovery or ingestion

3. **Multi-Signal Confidence Scoring**: Uses multiple lines of evidence to surface relationships with appropriate confidence levels during surfacing

4. **Simple Algorithm Registry**: Includes standard algorithms for confidence filtering, impact measurement, and health assessment, with the ability to extend in the future

5. **Complete Provenance Tracking**: Maintains full history of how information was discovered and connected

6. **Health and Sustainability Focus**: Goes beyond metrics to assess quality, sustainability, and community vitality

7. **Seamless Operation Flow**: Intelligently detects missing data during surfacing and offers smooth transition to discovery & ingestion

MOSS transforms our understanding of the research software landscape by making visible the previously hidden connections between code, publications, people, and institutions. It enables evidence-based decisions about software development, collaboration, and funding in the evolving open science ecosystem.