import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import pandas as pd
import requests

# Display example URLs for user guidance
print("""Example URLs: \n
        https://papers.ecosyste.ms/api/v1/projects/pypi/scikit-learn \n
        https://papers.ecosyste.ms/api/v1/projects/pypi/keras \n
        https://papers.ecosyste.ms/api/v1/projects/cran/OpenML \n
        https://papers.ecosyste.ms/api/v1/projects/cran/Imap  - 10 Mentions \n
        https://papers.ecosyste.ms/api/v1/projects/cran/gjam  - 1 Mention \n
        """)

# Prompt the user for project URL(s) and split the input into a list of URLs
project_url = input(
    'Please enter the ecosyste.ms URL for your project of interest: '
).split()

# Prompt the user to decide whether to include nodes for projects mentioned in related papers
process_comentioned_projects_yn = input(
    'Would you like to process every project co-mentioned in papers that mention your project? y/n: '
)


class SharedResources:
    """
    A thread-safe shared resource class for storing extracted data as Pandas DataFrames.
    Ensures concurrency safety using a threading lock.
    """

    def __init__(self):
        self.lock = Lock()
        self.institution_df = pd.DataFrame(columns=['ID', 'Label', 'Name', 'ROR'])
        self.people_df = pd.DataFrame(columns=['ID', 'Label', 'Name', 'ORCID'])
        self.paper_df = pd.DataFrame(
            columns=[
                'ID',
                'Label',
                'Name',
                'DOI',
                'Authors',
                'Projects Cited',
                'Sustainable Development Goals',
                'Concepts',
                'Domains',
                'Author Institutions',
            ]
        )
        self.project_df = pd.DataFrame(
            columns=['ID', 'Label', 'Name', 'Homepage', 'repository_url']
        )
        self.sdg_df = pd.DataFrame(columns=['ID', 'Label', 'Name'])
        self.concept_df = pd.DataFrame(
            columns=['ID', 'Label', 'Name', 'Wikidata', 'Concept_level']
        )
        self.domain_df = pd.DataFrame(columns=['ID', 'Label', 'Name', 'Is_major_topic'])
        self.project_url_set = set()


shared_resources = SharedResources()

headers = {'accept': 'application/json'}  # Headers for HTTP requests


# Function to process individual papers and extract relevant data
def process_paper(paper_url):
    """
    Fetch and process paper metadata from a given URL.
    Extracts and stores information on authors, institutions, SDGs, concepts, and domains.
    """
    try:
        paper_response = requests.get(paper_url, headers=headers, timeout=10)
        paper_dict = paper_response.json()

        if paper_dict['openalex_id'] not in shared_resources.paper_df['ID'].values:
            if paper_dict['openalex_data']:
                authors = parse_authors(paper_dict['openalex_data']['authorships'])
                institutions = parse_institutions(
                    paper_dict['openalex_data']['authorships']
                )
                sdgs = parse_sdgs(
                    paper_dict['openalex_data']['sustainable_development_goals']
                )
                concepts = parse_concepts(paper_dict['openalex_data']['concepts'])
                domains = parse_domains(paper_dict['openalex_data']['mesh'])
                paper_mentions = process_paper_mentions(paper_dict['mentions_url'])

                this_paper = pd.DataFrame(
                    [
                        {
                            'ID': paper_dict['openalex_id'],
                            'Label': 'Paper',
                            'Name': paper_dict['title'],
                            'DOI': paper_dict['doi'],
                            'Authors': ' | '.join(
                                authorship['author'].get('display_name', 'Unknown')
                                for authorship in paper_dict['openalex_data'][
                                    'authorships'
                                ]
                            ),
                            'Projects Cited': ' | '.join(paper_mentions),
                            'Sustainable Development Goals': ' | '.join(
                                sdg['display_name']
                                for sdg in paper_dict['openalex_data'][
                                    'sustainable_development_goals'
                                ]
                            ),
                            'Concepts': ' | '.join(
                                concept['display_name']
                                for concept in paper_dict['openalex_data']['concepts']
                            ),
                            'Domains': ' | '.join(
                                domain['descriptor_name']
                                for domain in paper_dict['openalex_data']['mesh']
                            ),
                            'Author Institutions': ' | '.join(
                                institution['display_name']
                                for auth in paper_dict['openalex_data']['authorships']
                                for institution in auth['institutions']
                            ),
                        }
                    ]
                )

                with shared_resources.lock:
                    shared_resources.institution_df = pd.concat(
                        [shared_resources.institution_df, institutions]
                    ).drop_duplicates(subset=['ID'])
                    shared_resources.people_df = pd.concat(
                        [shared_resources.people_df, authors]
                    ).drop_duplicates(subset=['ID'])
                    shared_resources.paper_df = pd.concat(
                        [shared_resources.paper_df, this_paper]
                    ).drop_duplicates(subset=['ID'])
                    shared_resources.sdg_df = pd.concat(
                        [shared_resources.sdg_df, sdgs]
                    ).drop_duplicates(subset=['ID'])
                    shared_resources.concept_df = pd.concat(
                        [shared_resources.concept_df, concepts]
                    ).drop_duplicates(subset=['ID'])
                    shared_resources.domain_df = pd.concat(
                        [shared_resources.domain_df, domains]
                    ).drop_duplicates(subset=['ID'])

    except requests.exceptions.RequestException as e:
        print(f'Request failed for paper {paper_url}: {e}')
    except json.decoder.JSONDecodeError as e:
        print(f'JSON decode error for paper {paper_url}: {e}')


def parse_authors(authorships):
    """
    Extracts author details from paper authorship metadata.
    """
    return pd.DataFrame(
        [
            {
                'ID': authorship['author']['id'],
                'Label': 'Person',
                'Name': authorship['author']['display_name'],
                'ORCID': authorship['author']['orcid'],
            }
            for authorship in authorships
        ]
    )


def parse_institutions(authorships):
    """
    Extracts instution details from paper authorship metadata.
    """
    return pd.DataFrame(
        [
            {
                'ID': inst['id'],
                'Label': 'Institution',
                'Name': inst['display_name'],
                'ROR': inst['ror'],
            }
            for auth in authorships
            for inst in auth['institutions']
        ]
    )


def parse_sdgs(sdgs_list):
    """
    Extracts sdg details from paper metadata.
    """
    return pd.DataFrame(
        [
            {
                'ID': sdg['id'],
                'Label': 'SDG',
                'Name': sdg['display_name'],
            }
            for sdg in sdgs_list
        ]
    )


def parse_concepts(concepts_list):
    """
    Extracts concept details from paper metadata.
    """
    return pd.DataFrame(
        [
            {
                'ID': concept['id'],
                'Label': 'Concept',
                'Name': concept['display_name'],
                'Wikidata': concept['wikidata'],
                'Concept_level': concept['level'],
            }
            for concept in concepts_list
        ]
    )


def parse_domains(domains_list):
    """
    Extracts domain details from paper metadata.
    """
    return pd.DataFrame(
        [
            {
                'ID': domain['descriptor_ui'],
                'Label': 'Domain',
                'Name': domain['descriptor_name'],
                'Is_major_topic': domain['is_major_topic'],
            }
            for domain in domains_list
        ]
    )


def process_paper_mentions(paper_mentions_url):
    """
    Fetches and extracts the names of projects mentioned in a paper, also collectiong their URLs for later recursion.
    """
    paper_mentions = []
    try:
        paper_mentions_response = requests.get(
            paper_mentions_url, headers=headers, timeout=10
        )
        paper_mentions_dict = paper_mentions_response.json()
        paper_mentions_list = [
            paper_mention['project_url'] for paper_mention in paper_mentions_dict
        ]
        with shared_resources.lock:
            shared_resources.project_url_set.update(paper_mentions_list)
        for project_url in paper_mentions_list:
            try:
                project_response = requests.get(
                    project_url, headers=headers, timeout=10
                )
                proj_dict = project_response.json()
                if 'ecosystem' in proj_dict:
                    paper_mentions.append(
                        f"{proj_dict['ecosystem']}:{proj_dict['name']}"
                    )
            except requests.exceptions.RequestException as e:
                print(f'Request failed for project {project_url}: {e}')
            except json.decoder.JSONDecodeError as e:
                print(f'JSON decode error for project {project_url}: {e}')
    except requests.exceptions.RequestException as e:
        print(f'Request failed for mentions {paper_mentions_url}: {e}')
    except json.decoder.JSONDecodeError as e:
        print(f'JSON decode error for mentions {paper_mentions_url}: {e}')
    return paper_mentions


def process_projects(project_urls):
    """
    Processes multiple project URLs concurrently using a thread pool.
    """
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(process_project, project_u) for project_u in project_urls
        ]
        for future in as_completed(futures):
            future.result()


def process_project(project_u):
    """
    Fetch and process project metadata from a given URL.
    Extracts and stores information on a single project, collects a list of paper urls, and initiates process_paper for each.
    """
    try:
        response = requests.get(project_u, headers=headers, timeout=10)
        project_dict = response.json()
        if project_dict['package']:
            home = project_dict['package']['homepage']
            repo = project_dict['package']['repository_url']
        else:
            home = ''
            repo = ''

        this_project = pd.DataFrame(
            [
                {
                    'ID': project_dict['czi_id'],
                    'Label': 'Project',
                    'Name': f"{project_dict['ecosystem']}:{project_dict['name']}",
                    'Homepage': home,
                    'repository_url': repo,
                }
            ]
        )

        with shared_resources.lock:
            shared_resources.project_df = pd.concat(
                [shared_resources.project_df, this_project]
            ).drop_duplicates(subset=['ID'])

        project_mentions_url = f"{project_dict['mentions_url']}?page=1&per_page=1000"
        mentions_response = requests.get(
            project_mentions_url, headers=headers, timeout=10
        )
        mentions_dict = mentions_response.json()
        print(f'Querying: {project_u}')
        print(
            f"There are {mentions_response.headers['total-pages']} pages of mentions to fetch."
        )
        print(f"For a total of: {mentions_response.headers['total-count']} papers")
        paper_urls_list = []
        total_pages = int(mentions_response.headers['total-pages'])
        for page_num in range(1, total_pages + 1):
            project_mentions_url = (
                f"{project_dict['mentions_url']}?page={page_num}&per_page=1000"
            )
            mentions_dict = requests.get(
                project_mentions_url, headers=headers, timeout=10
            ).json()
            paper_urls_list.extend([mention['paper_url'] for mention in mentions_dict])

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(process_paper, paper_url)
                for paper_url in paper_urls_list
            ]
            for future in as_completed(futures):
                future.result()

    except requests.exceptions.RequestException as e:
        print(f'Request failed for project {project_u}: {e}')
    except json.decoder.JSONDecodeError as e:
        print(f'JSON decode error for project {project_u}: {e}')


def write_to_csv():
    """
    Writes all collected data to CSV files.
    """
    with shared_resources.lock:
        shared_resources.institution_df.to_csv(
            'ecosystms_output_institutions.csv', index=False
        )
        shared_resources.people_df.to_csv('ecosystms_output_people.csv', index=False)
        shared_resources.paper_df.to_csv('ecosystms_output_papers.csv', index=False)
        shared_resources.project_df.to_csv('ecosystms_output_projects.csv', index=False)
        shared_resources.sdg_df.to_csv('ecosystms_output_sdgs.csv', index=False)
        shared_resources.concept_df.to_csv('ecosystms_output_concepts.csv', index=False)
        shared_resources.domain_df.to_csv('ecosystms_output_domains.csv', index=False)

        shared_resources.institution_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='w'
        )
        shared_resources.people_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='a'
        )
        shared_resources.paper_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='a'
        )
        shared_resources.project_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='a'
        )
        shared_resources.sdg_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='a'
        )
        shared_resources.concept_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='a'
        )
        shared_resources.domain_df.to_csv(
            'ecosystms_output_full.csv', index=False, mode='a'
        )


def write_to_parquet():
    """
    Writes all collected data to Parquet files for more efficient storage and retrieval.
    """
    with shared_resources.lock:
        shared_resources.institution_df.to_parquet(
            'institution.parquet', engine='pyarrow', index=False
        )
        shared_resources.people_df.to_parquet(
            'person.parquet', engine='pyarrow', index=False
        )
        shared_resources.paper_df.to_parquet(
            'paper.parquet', engine='pyarrow', index=False
        )
        shared_resources.project_df.to_parquet(
            'project.parquet', engine='pyarrow', index=False
        )
        shared_resources.sdg_df.to_parquet('sdg.parquet', engine='pyarrow', index=False)
        shared_resources.concept_df.to_parquet(
            'concept.parquet', engine='pyarrow', index=False
        )
        shared_resources.domain_df.to_parquet(
            'domain.parquet', engine='pyarrow', index=False
        )


# Main execution starts here

# Start processing the projects
process_projects(project_url)

# If the user opts to process co-mentioned projects, do so
if process_comentioned_projects_yn == 'y':
    project_url_set_copy = shared_resources.project_url_set.copy()
    process_projects(project_url_set_copy)

# Display the total number of co-mentioned projects found
print(f'This project had {len(shared_resources.project_url_set)} co-mentioned projects')

# Write the gathered data to CSV files
write_to_csv()
print('All rows appended to CSV files successfully!')

# Write the gathered data to Parquet files for more efficient storage
write_to_parquet()
print('All data exported to Parquet file successfully!')
