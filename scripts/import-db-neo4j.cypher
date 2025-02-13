//Clean House

//Delete Nodes & Relationships
MATCH (n) DETACH DELETE n;

//Drop Indices
DROP INDEX projectsByID IF EXISTS;
DROP INDEX institutionsByID IF EXISTS;
DROP INDEX personsByID IF EXISTS;
DROP INDEX papersByID IF EXISTS;
DROP INDEX sdgsByID IF EXISTS;
DROP INDEX conceptByID IF EXISTS;
DROP INDEX domainByID IF EXISTS;


//Import Institutions
LOAD CSV WITH HEADERS FROM "file:///institutions.csv" AS row
CREATE (n:Institution {
    ID: row.ID,
    Name: row.Name,
    ROR: row.ROR
});

//Import People
LOAD CSV WITH HEADERS FROM "file:///people.csv" AS row
CREATE (n:Person {
    ID: row.ID,
    Name: row.Name,
    ORCID: row.ORCID
});

//Import Papers
LOAD CSV WITH HEADERS FROM "file:///papers.csv" AS row
CREATE (n:Paper {
    ID: row.ID,
    Name: row.Name,
    DOI: row.DOI,
    Authors: split(row.Authors, ' | '),
    `Projects Cited`: split(row.`Projects Cited`, ' | '),
    `Sustainable Development Goals`: split(row.`Sustainable Development Goals`, ' | '),
    Concepts: split(row.Concepts, ' | '),
    Domains: split(row.Domains, ' | '),
    `Author Institutions`: split(row.`Author Institutions`, ' | ')
});

//Import Projects
LOAD CSV WITH HEADERS FROM "file:///projects.csv" AS row
CREATE (n:Project {
    ID: row.ID,
    Name: row.Name,
    Homepage: row.Homepage,
    repository_url: row.repository_url
});

//Import SDGs
LOAD CSV WITH HEADERS FROM "file:///sdgs.csv" AS row
CREATE (n:SDG {
    ID: row.ID,
    Name: row.Name
});

//Import Concepts
LOAD CSV WITH HEADERS FROM "file:///concepts.csv" AS row
CREATE (n:Concept {
    ID: row.ID,
    Name: row.Name,
    Wikidata: row.Wikidata,
    Concept_level: row.Concept_level
});

//Import Domains
LOAD CSV WITH HEADERS FROM "file:///domains.csv" AS row
CREATE (n:Domain {
    ID: row.ID,
    Name: row.Name,
    Is_major_topic: row.Is_major_topic
});


//Create Indices
CREATE INDEX projectsByID FOR (n:Project) ON (n.ID);
CREATE INDEX institutionsByID FOR (n:Institution) ON (n.ID);
CREATE INDEX personsByID FOR (n:Person) ON (n.ID);
CREATE INDEX papersByID FOR (n:Paper) ON (n.ID);
CREATE INDEX sdgsByID FOR (n:SDG) ON (n.ID);
CREATE INDEX conceptByID FOR (n:Concept) ON (n.ID);
CREATE INDEX domainByID FOR (n:Domain) ON (n.ID);
CALL db.awaitIndexes();


//create relationships
// Paper -> WRITTEN_BY -> Person
MATCH (n0:Paper)
UNWIND n0.Authors as i
MATCH (n1:Person)
WHERE n1.Name = i
MERGE (n0)-[:WRITTEN_BY]->(n1);

// Paper -> CITES -> Project
MATCH (n0:Paper)
UNWIND n0.`Projects Cited` as i
MATCH (n1:Project)
WHERE n1.Name = i
MERGE (n0)-[:CITES]->(n1);

// Paper -> ADDRESSES -> SDG
MATCH (n0:Paper)
UNWIND n0.`Sustainable Development Goals` as i
MATCH (n1:SDG)
WHERE n1.Name = i
MERGE (n0)-[:ADDRESSES]->(n1);

// Paper -> CONCEPTUALIZE -> Concept
MATCH (n0:Paper)
UNWIND n0.Concepts as i
MATCH (n1:Concept)
WHERE n1.Name = i
MERGE (n0)-[:CONCEPTUALIZE]->(n1);

// Paper -> IN_DOMAIN -> Domain
MATCH (n0:Paper)
UNWIND n0.Domains as i
MATCH (n1:Domain)
WHERE n1.Name = i
MERGE (n0)-[:IN_DOMAIN]->(n1);

// Paper -> AFFILIATED_WITH_INSTITUTION -> Institution
MATCH (n0:Paper)
UNWIND n0.`Author Institutions` as i
MATCH (n1:Institution)
WHERE n1.Name = i
MERGE (n0)-[:AFFILIATED_WITH_INSTITUTION]->(n1);
