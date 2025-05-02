//Clean House

//Delete Nodes & Relationships
MATCH (n) DETACH DELETE n;

//Drop Indices
DROP INDEX projectsByName IF EXISTS;
DROP INDEX peopleByName IF EXISTS;
DROP INDEX institutionsByName IF EXISTS;

//import nodes

/////////////////////////////////////////////IMPORT ALL ELEMENTS
LOAD CSV WITH HEADERS FROM "file:///UVM-MOSS.csv" AS row

CALL apoc.create.node([row.Type],
        CASE row.Type
                WHEN 'Project' THEN {
                        Name: row.Label,
                        Description: row.description,
                        Homepage: row.html_url,
                        Stargazers: row.stargazers,
                        Forks: row.forks,
                        `Created date`: row.created_at,
                        `Last Updated`: row.updated_at,
                        Contributors: split(row.contributors, ', '),
                        Is_scientific_project: row.is_scientific_project,
                        Dependencies: split(row.dependencies, ' | '),
                        Has_dependency_file: row.has_dependency_file,
                        Has_citation_cff: row.has_citation_cff,
                        Has_funding_json: row.has_funding_json,
                        Query: row.query,
                        Domains: split(row.Domains, ' | '),
                        `Domain Strength`: split(row.`Domain Strength`, ' | '),
                        Fields: split(row.Fields, ' | '),
                        `Field Strength`: split(row.`Field Strength`, ' | '),
                        `Associated Academic Institutions`: split(row.`Associated Academic Institutions`, ' | ')
                }
                WHEN 'Person' THEN {
                        Name: row.Label,
                        Homepage: row.html_url,
                        Domains: split(row.Domains, ' | '),
                        `Domain Strength`: split(row.`Domain Strength`, ' | '),
                        Fields: split(row.Fields, ' | '),
                        `Field Strength`: split(row.`Field Strength`, ' | '),
                        `Associated Academic Institutions`: split(row.`Associated Academic Institutions`, ' | '),
                        Bio: row.bio,
                        Public_repos: row.public_repos,
                        Followers: row.followers,
                        `Created date`: row.created_at,
                        `Last Updated`: row.updated_at,
                        `Predicted general connection/role`: row.`predicted general connection/role`,
                        `Additional predicted info`: row.`additional predicted info`,
                        //query? theres two columns named query...
                        Scientific_contributions: split(row.scientific_contributions, ' | '),
                        Non_scientific_contributions: split(row.non_scientific_contributions, ' | ')
                }                
                WHEN 'Academic Institution' THEN {
                        Name: row.Label                     
                }
                ELSE {
                        Name: row.Name
                }
        END
) YIELD node
RETURN node;


//Create Indices
CREATE INDEX projectsByName FOR (n:Project) ON (n.Name);
CREATE INDEX peopleByName FOR (n:Person) ON (n.Name);
CREATE INDEX institutionsByName FOR (n:`Academic Institution`) ON (n.Name);
CALL db.awaitIndexes();


//create relationships

// Project -> ASSOCIATED_WITH -> Academic Institution
MATCH (n0:Project)
UNWIND n0.`Associated Academic Institutions` as i
MATCH (n1:`Academic Institution`)
WHERE n1.Name = i
MERGE (n0)-[:ASSOCIATED_WITH]->(n1);

// Project <- CONTRIBUTES_TO <- Person
MATCH (n0:Project)
UNWIND n0.Contributors as i
MATCH (n1:Person)
WHERE n1.Name = i
MERGE (n1)-[:CONTRIBUTES_TO]->(n0);


