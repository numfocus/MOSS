import json
import csv
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Prompt for project URL(s)
projectURL = input("Please enter the ecosyste.ms URL for your project of interest: ").split()
#projectURL = ['https://papers.ecosyste.ms/api/v1/projects/pypi/scikit-learn']  #2431 mentions
#projectURL = ['https://papers.ecosyste.ms/api/v1/projects/pypi/keras']         #141 mentions
#projectURL = ['https://papers.ecosyste.ms/api/v1/projects/cran/OpenML']        #21 mentions
projectMentionsYN = input("Would you like to create nodes for every project mentioned in papers that mention your project? y/n: ")

# Declare global variables
rowList = []
institutionSet = set()
peopleSet = set()
paperSet = set()
projectSet = set()
sdgSet = set()

projectUrlSet = set()
headers = {'accept': 'application/json'}
myFieldnames = ['ID', 'Label', 'Name', 'ORCID', 'Persons Affiliated Institutions', 'DOI', 'Projects/Packages Cited', 'Authors', 'Homepage', 'repository_url', 'Sustainable Development Goals', 'sdg_score']

def processPaper(paperURL):
    paperResponse = requests.get(paperURL, headers=headers)
    try:
        paperDict = paperResponse.json()

        paperAuthorNames = []
        if paperDict["openalex_data"] is not None:
            for authorship in paperDict["openalex_data"]["authorships"]:
                paperAuthorNames.append(authorship['author']['display_name'])

        if projectMentionsYN == "y":
            paperMentions = processPaperMentions(paperDict["mentions_url"])
        else:
            paperMentions = ""

        if paperDict["openalex_id"] not in paperSet:
            paperSet.add(paperDict["openalex_id"])

            if paperDict["openalex_data"] is not None:
                for authorship in paperDict["openalex_data"]["authorships"]:
                    thisAuthorInstitutions = []
                    for institution in authorship["institutions"]:
                        thisAuthorInstitutions.append(institution['display_name'])
                        if institution["id"] not in institutionSet:
                            institutionSet.add(institution["id"])
                            rowList.append({'ID': institution['id'], 'Label': "Institution", 'Name': institution['display_name']})
                thisPaperSDGs = []
                for sdg in paperDict['openalex_data']['sustainable_development_goals']:
                    thisPaperSDGs.append(sdg['display_name'])
                    if sdg["id"] not in sdgSet:
                        sdgSet.add(sdg["id"])
                        rowList.append({'ID': sdg['id'], 'Label': "SDG", 'Name': sdg['display_name'], 'sdg_score': sdg['score']})

            rowList.append({'ID': paperDict['openalex_id'], 'Label': "Paper", 'Name': paperDict['title'], 'DOI': paperDict['doi'], 'Authors': " | ".join(paperAuthorNames), 'Projects/Packages Cited': " | ".join(paperMentions), 'Sustainable Development Goals': " | ".join(thisPaperSDGs)})
            authorDict = authorship["author"]
            if authorDict['id'] not in peopleSet:
                    peopleSet.add(authorDict['id'])
                    rowList.append({'ID': authorDict['id'], 'Label': "Person", 'Name': authorDict['display_name'], 'ORCID': authorDict['orcid'], 'Persons Affiliated Institutions': " | ".join(thisAuthorInstitutions)})
    except json.decoder.JSONDecodeError:
        paperAuthorNames = [] #meaningless

def processPaperMentions(paperMentionsURL):
    paperMentionsResponse = requests.get(paperMentionsURL, headers=headers)
    try:
        paperMentionsDict = paperMentionsResponse.json()

        paperMentionsList = []
        for paperMention in paperMentionsDict:
            paperMentionsList.append(paperMention["project_url"])
            projectUrlSet.add(paperMention["project_url"])

        thisPapersMentions = []
        for projectURL in paperMentionsList:
            projectResponse = requests.get(projectURL, headers=headers)
            try:
                projDict = projectResponse.json()

                thisPapersMentions.append(projDict["ecosystem"] + ":" + projDict["name"])

                if projDict["package"] is not None:
                    home = projDict["package"]["homepage"]
                    repo = projDict["package"]["repository_url"]
                else:
                    home = ""
                    repo = ""

                if projDict["czi_id"] not in projectSet:
                    projectSet.add(projDict["czi_id"])
                    rowList.append({'ID': projDict["czi_id"], 'Label': "Project", 'Name': projDict["ecosystem"] + ":" + projDict["name"], 'Homepage': home, 'repository_url': repo})
            except json.decoder.JSONDecodeError:
                thisPapersMentions = []
    except json.decoder.JSONDecodeError:
        thisPapersMentions = []

    return thisPapersMentions

def processProjects(projectURLs):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(processProject, projectU) for projectU in projectURLs]
        for future in as_completed(futures):
            future.result()

def processProject(projectU):
    response = requests.get(projectU, headers=headers)
    try:
        projectDict = response.json()

        if projectDict["package"] is not None:
            home = projectDict["package"]["homepage"]
            repo = projectDict["package"]["repository_url"]
        else:
            home = ""
            repo = ""

        projectSet.add(projectDict["czi_id"])
        rowList.append({'ID': projectDict["czi_id"], 'Label': "Project", 'Name': projectDict["ecosystem"] + ":" + projectDict["name"], 'Homepage': home, 'repository_url': repo})

        projectMentionsURL = projectDict["mentions_url"] + "?page=1&per_page=1000"

        mentionsResponse = requests.get(projectMentionsURL, headers=headers)
        mentionsDict = mentionsResponse.json()

        print("Querying: " + projectU)
        print("There are " + mentionsResponse.headers['total-pages'] + " pages of mentions to fetch.")
        print("For a total of: " + mentionsResponse.headers['total-count'] + " papers")

        paperURLsList = []
        totalPages = int(mentionsResponse.headers['total-pages'])
        pageNum = 1
        while pageNum <= totalPages:
            projectMentionsURL = projectDict["mentions_url"] + "?page=" + str(pageNum) + "&per_page=1000"
            mentionsDict = requests.get(projectMentionsURL, headers=headers).json()

            for mention in mentionsDict:
                paperURLsList.append(mention["paper_url"])
            pageNum += 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(processPaper, paperURL) for paperURL in paperURLsList]
            paperCounter = 0
            for future in as_completed(futures):
                future.result()
                paperCounter += 1
                print("Processed paper: " + str(paperCounter) + " of " + mentionsResponse.headers['total-count'])

        with open('ecosystms_output.csv', mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=myFieldnames)
            for row in rowList:
                writer.writerow(row)
        rowList.clear()
        print("All rows appended to CSV file successfully!")
    except json.decoder.JSONDecodeError:
        rowList.clear()


def checkScope():
    print("This project has " + str(len(projectUrlSet)) + " co-mentioned projects")

    mentionsCounts = []

    try:
        for projectU in projectUrlSet:
            response = requests.get(projectU, headers=headers)
            thisProjectDict = response.json()

            thisProjectMentionsURL = thisProjectDict["mentions_url"] + "?page=1&per_page=1"

            mentionsResponse = requests.get(thisProjectMentionsURL, headers=headers)
            mentionsDict = mentionsResponse.json()

            mentionsCounts.append(int(mentionsResponse.headers['total-count']))
            mentionsAverage = sum(mentionsCounts) / len(mentionsCounts)

        print("With an average of: " + str(mentionsAverage) + " mentions per project")
    except json.decoder.JSONDecodeError:
        mentionsCounts = [0]
    return(sum(mentionsCounts))



# Main
with open('ecosystms_output.csv', mode='w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=myFieldnames)
    writer.writeheader()

processProjects(projectURL)

papersEstimate = checkScope()

continueYN = input("Would you like to continue processing " + str(papersEstimate) + " more papers? y/n: ")

if continueYN == 'y':
    projUrlSetCopy = projectUrlSet.copy()
    processProjects(projUrlSetCopy)

