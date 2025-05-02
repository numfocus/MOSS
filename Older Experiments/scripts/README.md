## Getting Started
### Overview
 1. [Install neo4j desktop](https://neo4j.com/docs/desktop-manual/current/installation/download-installation/)
 2. Clone this repository
  ```
  git clone <repo-url>
  ```
 3. Collect data to add to your graph using `ecosyst.ms-api.py`
 4. Import data into neo4j using `import-db-neo4j`
 5. Query and visualize with neo4j Bloom

 ### Start data collection 
  1. Go to [ecosyst.ms](https://papers.ecosyste.ms/) and choose a project to analyze

> Try to find one under 200 mentions for the first try, then go larger
  1. Find the project's api url by trying out the ['/projects/{ecosystem}/{name}' query](https://papers.ecosyste.ms/docs/index.html)

![](../readme-assets/ecosystms-setup0.png)

  3. Open your terminal, navigate to the repository directory (or scripts) and run `ecosyst.ms-api.py` with [python3](https://www.python.org/downloads/)

![](../readme-assets/ecosystms-setup1.png)

  4. Paste the **Request URL** as the URL of interest; choose y, its more interesting but takes a little longer

![](../readme-assets/ecosystms-setup2.png)

  5. Once this is done you will have a **CSV file** to import into **neo4j**

 ### Install & setup neo4j desktop
  1. [Install neo4j desktop](https://neo4j.com/docs/desktop-manual/current/installation/download-installation/)
  
  2. Add a local DBMS to your project
  
  ![Add local DBMS](../readme-assets/neo4j-setup0.png)
  
  3. Name it anything, remember the password, press **create**

  ![](../readme-assets/neo4j-setup1.png)

  4. Edit the **settings** in the 3 dot menu to the right of your DBMS: uncomment 
  ```
  dbms.security.allow_csv_import_from_file_urls=true
  ```

  ![](../readme-assets/neo4j-allow-file-imports1.png)
  
  1. Start it and observe the **Bolt port** 

  ![](../readme-assets/neo4j-setup2.png)

  
  6. Open the Browser app

![](../readme-assets/neo4j-setup3.png)
![](../readme-assets/neo4j-setup4.png)

 ### Import your data to the graph database
  1. Open the **import folder** in your local filesystem

![](../readme-assets/neo4j-setup5.png)
  
  2. Copy the CSV file created by the `ecosyst.ms-api.py` script into the import directory

![](../readme-assets/moss-import0.png)

  3. Copy the contents of `import-db-neo4j` and paste into the shell in the browser app

![](../readme-assets/neo4j-setup6.png)

  4. Press the **blue play/run button** and this will import the rows of the CSV as nodes in the graph

![](../readme-assets/neo4j-setup7.png)

 ### Explore queries and visualizations
  1. Open neo4j Bloom the same way you opened the neo4j browser from neo4j desktop

![](../readme-assets/bloom-setup0.png)

  2. Form your first query in the top left

![](../readme-assets/bloom-setup2.png)

  3. Run it and see what happens! you can adjust max node count in setting in the bottom left

![](../readme-assets/bloom-setup1.png)

  4. If you add the graph data science plugin to your DBMS back in neo4j desktop, you can use those algorithms to change node size and other exciting things