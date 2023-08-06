import os 
import re 
import subprocess 
import json 

# Define directories and server names 
base_dir = os.getcwd() 
model_dir = os.path.join(base_dir, "power_bi", "Model")
m_file_dir = os.path.join(model_dir, "queries") 
sql_dir = os.path.join(base_dir, "SQL")  
on_prem_servers = ["dbreporting", "edwdmprod01", "branchreporting", "tmcbranchreporting"]

def get_file_paths(base_dir, sub_dir, file_ext): 
    """Get file paths with the specified extension in the subdirectory.""" 
    dir_path = os.path.join(base_dir, sub_dir) 
    return [os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith(file_ext)] 

def find_parentheses_and_remove_quotation_marks(text, search_pattern):
    """
    Identify the first open & closed pair of parentheses that contain the SQL Query
    Remove quotation marks and return the cleaned m_text
    """
    pos = 0
    open_bracket = 0
    for x in text[text.find(search_pattern):len(text)]:
        if x == "(":
            open_bracket += 1
        elif x == ")":
            open_bracket -= 1
            if open_bracket == 0 and pos > 1:
                text = re.sub(r"(?:\"\")","",text[0:pos]) + text[pos:len(text)] 
                break
        pos += 1
    return text

def extract_sql_from_m_file(m_file_path): 
    """Extract SQL query from .m file and return it as a string with metadata.""" 
    # Open up the m file and read it in
    with open(m_file_path,"r") as m_file:
        m_text = m_file.readlines()
        m_text = [x.strip() for x in m_text]
        m_text = ' '.join(m_text)
    # Remove all quotation marks inside query
    regex_replace = [
        (r"(?:\"\")", ""), # regular quotation mark
        (r"(?:'\"&)", "'&"), # beginning quotation mark for query parameters
        (r"(?:&\"')", "&'") # ending quotation mark for query parameters 
    ]
    for old, new in regex_replace:
        m_text = re.sub(old, new, m_text)
    # Search the .m file for an on-prem or snowflake query pattern and extract the SQL query
    on_prem_check = [m_text.lower().find(x) for x in on_prem_servers]
    if m_text.find("[Query=") >= 0 and any(x >= 0 for x in on_prem_check):
        raw_tsql = re.search(r"(?s)(?<=\[Query=\").*?(?=\")",m_text).group()
    else:
        raw_tsql = False
    if m_text.find("Source = Value.NativeQuery(Snowflake.Databases(") >= 0:
        raw_snowsql = re.search(r"(?s)(?<=\[Data\], \").*?(?=\")",m_text).group()
    else:
        raw_snowsql = False
    # Collect extracted query and associated metadata by SQL dialect
    file_name = os.path.basename(m_file_path)
    if raw_tsql:
        sql_query = {
            "query": raw_tsql, 
            "dialect": "tsql", 
            "name": file_name,
            "sql_name": "T-SQL"
        }
        print(f"{'*'*25} {file_name}: {sql_query['sql_name']} extracted {'*'*25}")
    elif raw_snowsql:
        sql_query = {
            "query": raw_snowsql, 
            "dialect": "snowflake", 
            "name": file_name,
            "sql_name": "SnowSQL"
        }
        print(f"{'*'*25} {file_name}: {sql_query['sql_name']} extracted {'*'*25}")
    else:
        sql_query = {
            "query": False, 
            "dialect": False, 
            "name": False,
            "sql_name": False
        }
        print(f"{'*'*25} {file_name}: No SQL query extracted {'*'*25}")
    return sql_query

def clean_sql_query(sql_query): 
    """Clean and format SQL query using the SQLFluff linter, then return it as a string.""" 
    # Search the SQL query for existing metadata, delete it if it already exists
    if bool(re.search(r"(?:-- User: ).*?(?:-- SQL File: ).*?(?:-- Power BI Report Name: ).*?(?:#\(lf\)#\(lf\))",sql_query["query"])):
        sql_query["query"] = re.sub(r"(?:-- User: ).*?(?:-- SQL File: ).*?(?:-- Power BI Report Name: ).*?(?:#\(lf\)#\(lf\))","",sql_query["query"])
    # Create new metadata
    user = os.environ["username"]
    sql_file_name = f"{sql_query['name'][:-2]}.sql"
    with open(f"{model_dir}\\database.json", "r") as json_file:
        name_lookup = json.load(json_file)
        report_name = name_lookup['name']
    metadata = f"-- User: {user}#(lf)-- SQL File: {sql_file_name}#(lf)-- Power BI Report Name: {report_name}#(lf)#(lf)"
    # Inject new metadata into the SQL query
    clean_sql = metadata + sql_query["query"]
    # Convert .m file character escape sequences to valid text equivalents
    regex_replace = [
        (r"(?:#\(cr,lf\))", "\\n"), # carriage return/line feed to newline
        (r"(?:#\(lf\))", "\\n"), # line feed to newline
        (r"(?:#\(tab\))", "    "), # tab character to actual tab
        (r"(?:#\(.*?\))", " "), # remove any other characters with the #(.) pattern
        (r"(?:'&)", "'\"&"), # add beginning quotation mark for query parameters
        (r"(?:&')", "&\"'") # add ending quotation mark for query parameters
    ]
    for old, new in regex_replace:
        clean_sql = re.sub(old, new, clean_sql)
    # Create or overwrite a file in the .\SQL folder then write the extracted SQL query to it
    with open(f"{sql_dir}\\{sql_file_name}","w") as sql_file:
        sql_file.write(clean_sql)
    # Run the SQL Linter with the correct dialect to clean up code formatting
    subprocess.run(f'sqlfluff fix "{sql_dir}\\{sql_file_name}" --dialect {sql_query["dialect"]} --force --exclude-rules AL05', shell=True)
    print(f"{'*'*25} {sql_query['name']}: {sql_query['sql_name']} linted {'*'*25}")
    # Open back up the linted SQL file and read it in
    with open(f"{sql_dir}\\{sql_file_name}","r") as sql_file:
        cleaned_sql_query = ''.join(sql_file.readlines()) # join list together into one string
    return cleaned_sql_query 

def inject_sql_into_m_file(m_file_path, cleaned_sql_query): 
    """Inject cleaned SQL query back into .m file.""" 
    m_file_name = os.path.basename(m_file_path)
    # Convert newlines, tabs, etc. back to their compatible .m file character escape sequences
    replace = [
        ("\r\n", "#(cr,lf)"), # carriage return/newline to #(cr,lf)
        ("\n", "#(lf)"), # newline to line feed 
        ("    ", "#(tab)"), # actual tab to tab character
    ]
    for old, new in replace:
        cleaned_sql_query = cleaned_sql_query.replace(old, new)
    # Open up the .m file and read it in
    with open(m_file_path,"r") as m_file:
        m_text = ''.join(m_file.readlines())
    # Remove query parameter quotation marks
    parameter_quotes = [(r"(?:'\"&)", "'&"), (r"(?:&\"')", "&'")]
    for old, new in parameter_quotes:
        m_text = re.sub(old, new, m_text)
    # Search for the relevant on-prem or snowflake query pattern and inject the linted SQL back into the .m file
    on_prem_check = [m_text.lower().find(x) for x in on_prem_servers]
    if m_text.find("[Query=") >= 0 and any(x >= 0 for x in on_prem_check):
        m_text = find_parentheses_and_remove_quotation_marks(m_text, "Sql.Database(")
        m_text = re.sub(r"(?s)(?<=\[Query=\").*?(?=\")",cleaned_sql_query,m_text)
        with open(m_file_path,"w") as m_file:
            m_file.write(m_text)
            print(f"{'*'*25} {m_file_name}: Linted T-SQL saved {'*'*25}")
    elif m_text.find("Source = Value.NativeQuery(Snowflake.Databases(") >= 0:
        m_text = find_parentheses_and_remove_quotation_marks(m_text, "NativeQuery(")
        m_text = re.sub(r"(?s)(?<=\[Data\], \").*?(?=\")",cleaned_sql_query,m_text)
        with open(m_file_path,"w") as m_file:
            m_file.write(m_text)
            print(f"{'*'*25} {m_file_name}: Linted SnowSQL saved {'*'*25}")

def main(): 
    """Format the SQL in a Power BI File to a universal standard""" 
    # Verify the SQL folder exists, create it if not 
    os.makedirs(sql_dir, exist_ok=True) 
    # If the Power BI file contains a data model with queries, run the program 
    if os.path.exists(m_file_dir): 
        m_files = get_file_paths(m_file_dir, "", ".m") 
        for m_file in m_files: 
            sql_query = extract_sql_from_m_file(m_file) 
            if sql_query["query"]:
                cleaned_sql_query = clean_sql_query(sql_query) 
                inject_sql_into_m_file(m_file, cleaned_sql_query) 
            
if __name__ == "__main__": 
    main()