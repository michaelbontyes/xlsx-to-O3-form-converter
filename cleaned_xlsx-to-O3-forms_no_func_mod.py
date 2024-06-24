import pandas as pd
import json
import os
import re

# Load the metadata
metadata_file = 'metadata.xlsx'
# Adjust header to start from row 2
option_sets = pd.read_excel(metadata_file, sheet_name='OptionSets', header=1)
sheets = ['F01-MHPSS_Baseline', 'F02-MHPSS_Follow-up']

# Print the columns in the OptionSets sheet to verify
#print(f"Columns in OptionSets sheet: {option_sets.columns.tolist()}")

# Function to fetch options for a given option set
def get_options(option_set_name):
    return option_sets[option_sets['OptionSet name'] == option_set_name].to_dict(orient='records')

# Function to safely parse JSON
def safe_json_loads(s):
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None

# Manage rendering options
def manage_rendering(rendering, validation_format):
    if rendering == 'coded':
        rendering = 'radio'
    elif rendering == 'coded' and validation_format == 'multiple choice':
        rendering = 'radio'
    elif rendering == 'boolean':
        rendering = 'radio'
    elif rendering == 'numeric':
        rendering = 'numeric'
    elif rendering == 'text':
        rendering = 'text'
    return rendering

# Manage labels
def manage_label(original_label):
    # Clean the label
    label = remove_prefixes(original_label)
    # Remove any other non-alphanumeric characters except spaces, (), -, _, /, ., <, and >
    label = re.sub(r'[^a-zA-Z0-9\s\(\)\-_\/\.<>]', '', label)
    # Remove leading ". " prefixes
    label = re.sub(r'^\.\s*', '', label)
    return label

# Manage IDs
def manage_id(original_id, id_type="question", question_id="None"):
    # Clean the ID
    id = remove_prefixes(original_id)
    id = re.sub(r'\s*\(.*?\)', '', id)
    id = re.sub(r'/', ' Or ', id) # Replace "/" with "Or"
    if not detect_range_prefixes(id):
        id = re.sub(r'-', ' ', id) # Replace "-" with a space
        id = re.sub(r'_', ' ', id) # Replace "_" with a space
    id = re.sub(r'-', 'To', id) # Replace "-"
    id = re.sub(r'<', 'Less Than', id) # Replace "<"
    id = re.sub(r'>', 'More Than', id) # Replace "<"
    id = camel_case(id)
    id = re.sub(r'[^a-zA-Z0-9_-]', '', id)  # Remove any other non-alphanumeric characters
    id = re.sub(r'^_+|_+$', '', id)  # Remove leading and trailing underscores
    id = re.sub(r'_+', '_', id)  # Replace multiple underscores with a single underscore
    if id_type == "answer" and id == 'other':
        id = question_id+id.capitalize()
    return id

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
    pattern = r"(\d+-\d+|\> \d+|< \d+|\d+ - \d+|\d+-\d+)"
    matches = re.findall(pattern, text)
    return bool(matches)

def camel_case(text):
    words = text.split()
    camel_case = words[0].lower()
    for word in words[1:]:
        camel_case += word.capitalize()
    return camel_case

# Function to modify skip logic expressions
def build_skip_logic_expression(expression: str) -> str:
    # Regex pattern to match the required parts
    pattern = r"\[([^\]]+)\]\s*(<>|!==|==)\s*'([^']*)'"
    match = re.search(pattern, expression)

    if match:
        question_id, operator, conditional_answer = match.groups()
        if operator == '<>':
            operator = '!=='
        elif operator != '!==':
            return 'Only conditional operator "different than" noted !== is supported'

        question_id = manage_id(question_id)
        conditional_answer = manage_id(conditional_answer, id_type="answer", question_id=question_id)

        return f"{question_id} {operator} '{conditional_answer}'"
    else:
        return "Invalid expression format"

# Function to generate question JSON
def generate_question(row, columns, concept_ids):
    if row.isnull().all() or pd.isnull(row['Question']):
        return None  # Skip empty rows or rows with empty 'Question'

    # Manage values and default values
    original_question_label = row['Label if different'] if 'Label if different' in columns and pd.notnull(row['Label if different']) else row['Question']
    question_label = manage_label(original_question_label)
    question_id = manage_id(original_question_label)
    question_concept_id = row['External ID'] if 'External ID' in columns and pd.notnull(row['External ID']) else question_id
    question_type = "obs"
    question_datatype = row['Datatype'].lower() if pd.notnull(row['Datatype']) else 'radio'
    validation_format = row['Validation (format)'] if 'Validation (format)' in columns and pd.notnull(row['Validation (format)']) else ''
    question_required = str(row['Mandatory']).lower() == 'true' if 'Mandatory' in columns and pd.notnull(row['Mandatory']) else False
    question_rendering = manage_rendering(question_datatype, validation_format)
    question_validators = safe_json_loads(row['Validation (format)'] if 'Validation (format)' in columns and pd.notnull(row['Validation (format)']) else '')

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
                "concept": opt['External ID'] if 'External ID' in columns and pd.notnull(opt['External ID']) else manage_id(opt['Answers'], id_type="answer", question_id=question_id),
            } for opt in options
        ]

    return question

# Function to generate form JSON
def generate_form(sheet_name):
    form = {
        "name": sheet_name,
        "pages": []
    }

    df = pd.read_excel(metadata_file, sheet_name=sheet_name, header=1)  # Adjust header to start from row 2
    # print(f"Columns in {sheet_name} sheet: {df.columns.tolist()}")  # Display the columns in the sheet
    columns = df.columns.tolist()

    concept_ids = set()  # Initialize a set to keep track of concept IDs

    sections = df['Section'].unique()
    for section in sections:
        section_df = df[df['Section'] == section]
        section_label = section_df['Section'].iloc[0] if pd.notnull(section_df['Section'].iloc[0]) else ''
        questions = [generate_question(row, columns, concept_ids) for _, row in section_df.iterrows() if not row.isnull().all() and pd.notnull(row['Question'])]
        questions = [q for q in questions if q is not None]

        form["pages"].append({
            "label": f"Page {len(form['pages']) + 1}",
            "sections": [{
                "label": section_label,
                "isExpanded": "true",
                "questions": questions
            }]
        })

    return form, concept_ids

import re

# Generate forms and save as JSON
output_dir = './forms'
os.makedirs(output_dir, exist_ok=True)

all_concept_ids = set()
all_forms = []

for sheet in sheets:
    form, concept_ids = generate_form(sheet)
    json_data = json.dumps(form, indent=4)
    try:
        json.loads(json_data)  # Validate JSON format
        with open(os.path.join(output_dir, f"{sheet}.json"), 'w') as f:
            f.write(json_data)
        print(f"Form for sheet {sheet} generated successfully!")
    except json.JSONDecodeError as e:
        print(f"JSON format error in form generated from sheet {sheet}: {e}")

    all_concept_ids.update(concept_ids)
    all_forms.append(form)

#check_missing_concepts(all_forms, all_concept_ids)
print("Forms generation completed!")
