"""
A script to generate OpenMRS 3 forms from a metadata file in Excel.
"""
import json
import os
import re
import pandas as pd

# Load the metadata
METADATA_FILE = 'metadata.xlsx'
# Adjust header to start from row 2
option_sets = pd.read_excel(METADATA_FILE, sheet_name='OptionSets', header=1)
sheets = ['F01-MHPSS_Baseline', 'F02-MHPSS_Follow-up']

# Print the columns in the OptionSets sheet to verify
# print(f"Columns in OptionSets sheet: {option_sets.columns.tolist()}")

# Function to fetch options for a given option set
def get_options(option_set_name):
    """
    Fetch options for a given option set name.
    
    Args:
        option_set_name (str): The name of the option set.

    Returns:
        list: A list of dictionaries containing option set details.
    """
    return option_sets[option_sets['OptionSet name'] == option_set_name].to_dict(orient='records')

def safe_json_loads(s):
    """
    Safe json loads.
    """
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None

def manage_rendering(rendering, validation_format):
    """
    Manage rendering options.
    """
    if rendering == 'coded':
        rendering = 'radio'
    elif rendering == 'coded' and validation_format == 'multiple choice':
        rendering = 'radio'
    elif rendering == 'coded' and validation_format == 'select extended':
        rendering = 'radio'
    elif rendering == 'boolean':
        rendering = 'radio'
    elif rendering == 'numeric':
        rendering = 'numeric'
    elif rendering == 'text':
        rendering = 'text'
    return rendering

def manage_label(original_label):
    """
    Manage labels.

    Args:
        original_label (str): The original label.

    Returns:
        str: The cleaned label.
    """
    # Clean the label
    label = remove_prefixes(original_label)
    # Remove any other non-alphanumeric characters except spaces, (), -, _, /, ., <, and >
    label = re.sub(r'[^a-zA-Z0-9\s\(\)\-_\/\.<>]', '', label)
    # Remove leading ". " prefixes
    label = re.sub(r'^\.\s*', '', label)
    return label

# Manage IDs
def manage_id(original_id, id_type="question", question_id="None"):
    """
        Manage IDs.

    Args:
        original_id (str): The original ID.
        id_type (str, optional): The ID type. Defaults to "question".
        question_id (str, optional): The question ID. Defaults to "None".

    Returns:
        str: The cleaned ID.
    """
    cleaned_id = remove_prefixes(original_id)
    cleaned_id = re.sub(r'\s*\(.*?\)', '', cleaned_id)
    # Replace "/" with "Or"
    cleaned_id = re.sub(r'/', ' Or ', cleaned_id)
    if not detect_range_prefixes(cleaned_id):
        # Replace "-" with a space
        cleaned_id = re.sub(r'-', ' ', cleaned_id)
        # Replace "_" with a space
        cleaned_id = re.sub(r'_', ' ', cleaned_id)
    # Replace "-"
    cleaned_id = re.sub(r'-', 'To', cleaned_id)
    # Replace "<"
    cleaned_id = re.sub(r'<', 'Less Than', cleaned_id)
    # Replace "<"
    cleaned_id = re.sub(r'>', 'More Than', cleaned_id)
    cleaned_id = camel_case(cleaned_id)
    # Remove any other non-alphanumeric characters
    cleaned_id = re.sub(r'[^a-zA-Z0-9_-]', '', cleaned_id)
    # Remove leading and trailing underscores
    cleaned_id = re.sub(r'^_+|_+$', '', cleaned_id)
    # Replace multiple underscores with a single underscore
    cleaned_id = re.sub(r'_+', '_', cleaned_id)
    if id_type == "answer" and cleaned_id == 'other':
        cleaned_id = question_id+cleaned_id.capitalize()
    return cleaned_id

def remove_prefixes(text):
    """
    Remove numerical prefixes from the beginning of the string.
    Examples of prefixes: "1. ", "1.1 ", "1.1.1 ", etc.

    Parameters:
    text (str): The input string from which to remove prefixes.

    Returns:
    str: The string with the prefixes removed.
    """
    if not detect_range_prefixes(text):
        # Use re.sub to remove the matched prefix
        text = re.sub(r'^\d+(\.\d+)*\s*', '', text)
    return text

def detect_range_prefixes(text):
    """
    Detect ranges in the beginning of the string.
    """
    pattern = r"(\d+-\d+|\> \d+|< \d+|\d+ - \d+|\d+-\d+)"
    matches = re.findall(pattern, text)
    return bool(matches)

def camel_case(text):
    """
    Camel case a string.
    """
    words = text.split()
    camel_case_text = words[0].lower()  # Move this line outside the function
    for word in words[1:]:
        camel_case_text += word.capitalize()
    return camel_case_text

def build_skip_logic_expression(expression: str) -> str:
    """
    Build a skip logic expression from an expression string.

    Args:
        expression (str): An expression string.

    Returns:
        str: A skip logic expression.
    """
    # Regex pattern to match the required parts
    pattern = r"\[([^\]]+)\]\s*(<>|!==|==)\s*'([^']*)'"
    match = re.search(pattern, expression)

    if match:
        question_id, operator, cond_answer = match.groups()
        if operator == '<>':
            operator = '!=='
        elif operator != '!==':
            return 'Only conditional operator "different than" noted !== is supported'

        question_id = manage_id(question_id)
        cond_answer = manage_id(cond_answer, id_type="answer", question_id=question_id)

        return f"{question_id} {operator} '{cond_answer}'"
    return "Invalid expression format"

def generate_question(row, columns):
    """
        Generate a question JSON from a row of the OptionSets sheet.

    Args:
        row (pandas.Series): A row of the OptionSets sheet.
        columns (list): A list of column names in the OptionSets sheet.

    Returns:
        dict: A question JSON.
    """
    if row.isnull().all() or pd.isnull(row['Question']):
        return None  # Skip empty rows or rows with empty 'Question'

    # Manage values and default values
    original_question_label = (row['Label if different'] if 'Label if different' in columns and
                            pd.notnull(row['Label if different']) else row['Question'])

    question_label = manage_label(original_question_label)
    question_id = manage_id(original_question_label)

    question_concept_id = (row['External ID'] if 'External ID' in columns and
                        pd.notnull(row['External ID']) else question_id)

    question_type = "obs"

    question_datatype = (row['Datatype'].lower() if pd.notnull(row['Datatype']) else 'radio')

    validation_format = (row['Validation (format)'] if 'Validation (format)' in columns and
                        pd.notnull(row['Validation (format)']) else '')

    question_required = (str(row['Mandatory']).lower() == 'true' if 'Mandatory' in columns and
                        pd.notnull(row['Mandatory']) else False)

    question_rendering = manage_rendering(question_datatype, validation_format)

    question_validators = safe_json_loads(validation_format)

    # Build the question JSON
    question = {
        "label": question_label,
        "type": question_type,
        "required": question_required,
        "id": question_id,
        "questionOptions": {
            "rendering": question_rendering,
            "concept": question_concept_id
        },
        "validators": question_validators
    }

    if 'Default value' in columns and pd.notnull(row['Default value']):
        question['default'] = row['Default value']

    if 'Question' in columns and pd.notnull(row['Question']):
        question['questionInfo'] = question_label

    if 'Calculation' in columns and pd.notnull(row['Calculation']):
        question['questionOptions']['calculate'] = {"calculateExpression": row['Calculation']}

    if 'Skip logic' in columns and pd.notnull(row['Skip logic']):
        question['hide'] = {"hideWhenExpression": build_skip_logic_expression(row['Skip logic'])}

    if 'OptionSet name' in columns and pd.notnull(row['OptionSet name']):
        options = get_options(row['OptionSet name'])
        question['questionOptions']['answers'] = [
            {
                "label": manage_label(opt['Answers']),
                "concept": (opt['External ID'] if 'External ID' in columns and 
                            pd.notnull(opt['External ID'])
                            else manage_id(opt['Answers'], id_type="answer",
                                        question_id=question_id)),
            } for opt in options
        ]

    return question

def generate_form(sheet_name):
    """
    Generate a form JSON from a sheet of the OptionSets sheet.

    Args:
        sheet_name (str): The name of the sheet in the OptionSets sheet.

    Returns:
        dict: A form JSON.
    """
    form_data = {
        "name": sheet_name,
        "description": "MSF Form - "+sheet_name,
        "version": "1",
        "published": True,
        "uuid": "",
        "processor": "EncounterFormProcessor",
        "encounter": "Consultation",
        "retired": False,
        "referencedForms": [],
        "pages": []
    }

    # Adjust header to start from row 2
    df = pd.read_excel(METADATA_FILE, sheet_name=sheet_name, header=1)
    columns = df.columns.tolist()

    # concept_ids is defined here, not inside the function
    concept_ids_set = set()

    sections = df['Section'].unique()
    for section in sections:
        section_df = df[df['Section'] == section]
        section_label = (section_df['Section'].iloc[0] if pd.notnull(section_df['Section'].iloc[0])
                        else '')

        questions = [generate_question(row, columns)
                    for _, row in section_df.iterrows()
                    if not row.isnull().all() and pd.notnull(row['Question'])]

        questions = [q for q in questions if q is not None]

        form_data["pages"].append({
            "label": f"Page {len(form_data['pages']) + 1}",
            "sections": [{
                "label": section_label,
                "isExpanded": "false",
                "questions": questions
            }]
        })

    return form_data, concept_ids_set

# Generate forms and save as JSON
OUTPUT_DIR = './forms'
os.makedirs(OUTPUT_DIR, exist_ok=True)

all_concept_ids = set()
all_forms = []

for sheet in sheets:
    form, concept_ids = generate_form(sheet)
    json_data = json.dumps(form, indent=4)
    try:
        json.loads(json_data)  # Validate JSON format
        with open(os.path.join(OUTPUT_DIR, f"{sheet}.json"), 'w', encoding='utf-8') as f:
            f.write(json_data)
        print(f"Form for sheet {sheet} generated successfully!")
    except json.JSONDecodeError as e:
        print(f"JSON format error in form generated from sheet {sheet}: {e}")

    all_concept_ids.update(concept_ids)
    all_forms.append(form)

#check_missing_concepts(all_forms, all_concept_ids)
print("Forms generation completed!")
