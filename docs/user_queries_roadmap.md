---
title: Additional MOSS queries
author: Victor Lu
date: April 30, 2025
---


I  believe this is the original paper for this “OMSF user journey”   
[https://arxiv.org/pdf/2209.00693](https://arxiv.org/pdf/2209.00693)

Here are some  additional, related queries that build on the idea of tracing software impact through mentions, contributors, and domains

#### **Mention-Level & Disambiguation Questions**

1. **What are the most common variants of how a project’s software is mentioned in papers?**  
    (Helps refine name disambiguation and improve citation tracking accuracy.)

2. **Which projects are often confused with or co-mentioned alongside OMSF projects?**  
    (Useful for clustering related tools and understanding semantic overlap.)

3. **What percent of software mentions in papers fail to resolve to a known repository?**  
    (Helps identify missing metadata or opportunities for repo-linking improvements.)

#### **🧬 Metadata-Enhanced Questions**

4. **Which software tools that cite OMSF projects are themselves cited heavily?**  
    (Second-order citation — helps measure *downstream propagation* of influence.)

5. **What are the most common journals, conferences, or domains citing software that also cite OMSF projects?**  
    (Can surface adjacent or emerging research communities.)

6. **How many OMSF-related software mentions are linked to publications with missing or ambiguous DOIs?**  
    (May highlight places where metadata improvements are needed.)

#### **👥 Community Structure & Knowledge Flow**

7. **Which authors appear in multiple papers that mention different OMSF projects?**  
    (Identifies cross-project integrators or latent experts.)

8. **What percentage of contributors to software mentioned in papers citing OMSF projects are *new* to research software development?**  
    (Early signals of developer community growth or outreach success.)

9. **Are there identifiable "on-ramps" into OMSF software ecosystems based on co-citation or contributor flow?**  
    (Could help design better community engagement or onboarding.)

#### **🌐 Graph-Based Structure Queries**

10. **Which software tools form bridges between otherwise disconnected clusters of research topics?**  
     (Reveal *high betweenness centrality* nodes — i.e., key integrative software.)

11. **What is the average path length between an OMSF project and other commonly used biomedical tools in citation graphs?**  
     (A proxy for software reach or ecosystem centrality.)

12. **Which software tools are consistently cited *with* OMSF projects but have no direct code-level dependencies?**  
     (Uncover complementary or co-evolving research software.)

Goal:  
Determine the importance of their project  
	 \- Determine the contributor affiliations of their project  
	 \- Determine the gravity of their project  
		\- Does the project attract outside contributors?  
 \- Determine reach of software across research ecosystem

	\- Can utilizing classical graph theory

	  
1\. Go to website

2\. Option to login

3\. If not login, given limited presets and limited subgraph visualization of major projects/papers/nodes

4\. If login, given wider access

5\. Given option for direct query or visualization or a data dashboard on a project

6\. They can choose preset queries or custom queries

7\. If their query pulls data that does not exist, they are given a notice  
 \- We (backend) get a notification so we can go pull that data

8\. If direct query  
 \- They ask question  
 \- They get answer  
 \- They get customized visualization

9\. If visualization  
 \- toggle different nodes  
 \- resize nodes  
 \- toggle relationships  
 \- bar-chart/pivot-table in different 

Query Example:

* How many contributors come from organizations outside of OMSF?  
* How many papers cite OMSF projects?  
* Of the authors of the papers that cite OMSF projects, how many of them publish in domains not directly associated with OMSF projects?

- Jon to reach out to Ethan get user questions  
- Jon to sketch out what data is necessary to answer Ethan’s questions  
  - For review next week  
- Mark to create PR for new ecosystems script  
- Mark to review other PR requests  
- Jon to review Daves PR comments  
- Sam to create a PR  
  - Boris, Dave, Guy, and Max to do PR review  
- Jon to add all of these to project board  
- Sam to price out linux box (2 weeks)  
- Continuing  
  - Consider infrastructure as code  
  - Consider consequences of receiving funding  
  - Consider governance

Determine funding sources of their ecosystem  
Determine the impact of various funding cycles 	to their software  
Perform a security and health analysis of their projects and ecosystem

Folder structure as PR

—------------------

Wants:

* Front end to scrape  
* Higher speed \-- subgraphs?  
* Rest API they can query / Host themselves  
* Dashboard  
  * As a datasource

Core struggles

* Finding the data sources and APIs  
* Data infrastructure and management  
* Aggregating resources that don't want to be aggregated  
* "I'd much rather write software to pull the data I need from one resource rather than writing software to pull from 12 different resources".

Hard data interactions

* DOIs  
* Repos  
* Papers  
* GitHub Data  
* Individual contributor data and stories  
  * Identify heros to help facilitate them  
    * Do they contribute to other projects?  
  * Repo gravity  
* "Papers that are used in the same research"  
* Relationships between repositories  
  * Repo has a DOI that references another repo  
    * Repos referenced by papers that reference the first paper  
* How many repos are using our repo  
* Dependency graphing sboms  
* Repo interrelations  
  * Dependencies  
  * Extension/built-on  
  * Complementary in research  
* Contributor information  
* "we're on a repo, search for all repos using our repo, then another layer, do those respos use our repo"  
* Less need for topics

**"How do we map the mental dependency on why we wrote a piece of code that we did"**  
