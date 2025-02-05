import kuzu
import pandas as pd

# Define the file path for your CSV file
input_data_folder = '/home/mark/Source/myRepos/eyermt/git-decofusion/moss/scripts/kuzu_pipeline_test/'  # Replace with your actual file path

"""
# Read the CSV file into a Pandas DataFrame
institutions_data = pd.read_csv(input_data_folder + "ecosystms_output_institutions.csv")
people_data = pd.read_csv(input_data_folder + "ecosystms_output_people.csv")
papers_data = pd.read_csv(input_data_folder + "ecosystms_output_papers.csv")
projects_data = pd.read_csv(input_data_folder + "ecosystms_output_projects.csv")
sdgs_data = pd.read_csv(input_data_folder + "ecosystms_output_sdgs.csv")
concepts_data = pd.read_csv(input_data_folder + "ecosystms_output_concepts.csv")
domains_data = pd.read_csv(input_data_folder + "ecosystms_output_domains.csv")
"""

# Read the parquet files into a Pandas DataFrame
institutions_data = pd.read_parquet(input_data_folder + "institution.parquet")
people_data = pd.read_parquet(input_data_folder + "person.parquet")
papers_data = pd.read_parquet(input_data_folder + "paper.parquet")
projects_data = pd.read_parquet(input_data_folder + "project.parquet")
sdgs_data = pd.read_parquet(input_data_folder + "sdg.parquet")
concepts_data = pd.read_parquet(input_data_folder + "concept.parquet")
domains_data = pd.read_parquet(input_data_folder + "domain.parquet")


print("Data loaded from file")

institutions = institutions_data.drop_duplicates(subset=['ID'])
people = people_data.drop_duplicates(subset=['ID'])
papers = papers_data.drop_duplicates(subset=['ID'])
projects = projects_data.drop_duplicates(subset=['ID'])
sdgs = sdgs_data.drop_duplicates(subset=['ID'])
concepts = concepts_data.drop_duplicates(subset=['ID'])
domains = domains_data.drop_duplicates(subset=['ID'])

print("Duplicates removed")

# Start kuzu db and establish connection
db = kuzu.Database("moss-kuzu-db")
conn = kuzu.Connection(db)

print("Kuzu connection established")

# Create node schema
conn.execute("CREATE NODE TABLE Institution(ID STRING, Label STRING, Name STRING, ROR STRING, PRIMARY KEY (ID))")
conn.execute("CREATE NODE TABLE Person(ID STRING, Label STRING, Name STRING, ORCID STRING, PRIMARY KEY (ID))")
conn.execute("CREATE NODE TABLE Paper(ID STRING, Label STRING, Name STRING, DOI STRING, Authors STRING, Projects_Cited STRING, Sustainable_Development_Goals STRING, Concepts STRING, Domains STRING, Author_Institutions STRING, PRIMARY KEY (ID))")
conn.execute("CREATE NODE TABLE Project(ID STRING, Label STRING, Name STRING, Homepage STRING, repository_url STRING, PRIMARY KEY (ID))")
conn.execute("CREATE NODE TABLE SDG(ID STRING, Label STRING, Name STRING, PRIMARY KEY (ID))")
conn.execute("CREATE NODE TABLE Concept(ID STRING, Label STRING, Name STRING, Wikidata STRING, Concept_level STRING, PRIMARY KEY (ID))")
conn.execute("CREATE NODE TABLE Domain(ID STRING, Label STRING, Name STRING, Is_major_topic BOOL, PRIMARY KEY (ID))")

print("Node schema created")

# Import nodes to kuzu
result = conn.execute("LOAD FROM institutions RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY Institution FROM institutions (ignore_errors=true)")
print("Institutions imported successfully")

result = conn.execute("LOAD FROM people RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY Person FROM people (ignore_errors=true)")
print("People imported successfully")

result = conn.execute("LOAD FROM papers RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY Paper FROM papers")
print("Papers imported successfully")

result = conn.execute("LOAD FROM projects RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY Project FROM projects")
print("Projects imported successfully")

result = conn.execute("LOAD FROM sdgs RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY SDG FROM sdgs")
print("SDGs imported successfully")

result = conn.execute("LOAD FROM concepts RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY Concept FROM concepts")
print("Concepts imported successfully")

result = conn.execute("LOAD FROM concepts RETURN * LIMIT 5")
print(result.get_as_df())
conn.execute("COPY Domain FROM domains")
print("Domains imported successfully")


#result = conn.execute("LOAD FROM people RETURN * LIMIT 5")
#print(result.get_as_df())
#conn.execute("COPY Person FROM people (ignore_errors=true)")
#print("People imported successfully")


print("All Nodes imported successfully")

# Test that its there
result = conn.execute("MATCH (n:SDG) RETURN n.*")
print(result.get_as_df())

