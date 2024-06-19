import pandas as pd
import json
import os
from uuid import uuid4
import re

# Load the metadata
metadata_file = 'metadata.xlsx'
option_sets = pd.read_excel(metadata_file, sheet_name='OptionSets', header=1)  # Adjust header to start from row 2
sheets = ['F01-MHPSS_Baseline', 'F02-MHPSS_Follow-up']

# Print the columns in the OptionSets sheet to verify
#print(f"Columns in OptionSets sheet: {option_sets.columns.tolist()}")

# Function to fetch options for a given option set
def get_options(option_set_name):
    return option_sets[option_sets['OptionSet name'] == option_set_name].to_dict(orient='records')

def camel_case(text):
    words = text.split()
    camel_case = words[0].lower()
    for word in words[1:]:
        camel_case += word.capitalize()
    return camel_case

# Function to clean up text for labels and IDs
def clean_text(text, type=''):
    if pd.isnull(text):
        return ''
    text = str(text)
    if type == 'question_label':
        text = re.sub(r'^\d+([.,]\d+)?\s*|\.\s*', '', text)  # Remove numerical prefixes like "1. ", "2 ", "0 - ", "1 - "
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
        return text
    if type == 'id':
        text = camel_case(text)
        text = re.sub(r'\s*-\s*', '_', text)  # Replace hyphen surrounded by spaces with underscore
        text = re.sub(r'[^a-zA-Z0-9_]', '', text)  # Remove any other non-alphanumeric characters
        text = re.sub(r'^_+|_+$', '', text)  # Remove leading and trailing underscores
        text = re.sub(r'_+', '_', text)  # Replace multiple underscores with a single underscore
        return text
    if type == 'question_answer_label':
        text = re.sub(r'^\d+([.,]\d+)?\s*|\.\s*', '', text)  # Remove numerical prefixes like "1. ", "2 ", "0 - ", "1 - "
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
        return text
    else:
        text = re.sub(r'[^a-zA-Z0-9\s\(\)\-_\/]', '', text)  # Remove any other non-alphanumeric characters except spaces, (), -, _, and /
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
        return text

# Function to generate an external ID
def generate_external_id():
    return str(uuid4())

# Function to modify skip logic expressions
def build_skip_logic_expression(expression: str) -> str:
    # Regex pattern to match the required parts
    pattern = r"\[([^\]]+)\]\s*(<>|!==|==)\s*'([^']*)'"
    match = re.search(pattern, expression)
    
    if match:
        question_id, operator, conditional_answer = match.groups()
        conditional_answer = clean_text(conditional_answer, type='question_answer_label')
        question_id_camel = camel_case(question_id)
        return f"{question_id_camel} {operator} '{conditional_answer}'"
    else:
        return "Invalid expression format"

# Function to safely parse JSON
def safe_json_loads(s):
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None

# Function to generate question JSON
def generate_question(row, columns, concept_ids):
    if row.isnull().all() or pd.isnull(row['Question']):
        return None  # Skip empty rows or rows with empty 'Question'
    
    cleaned_question_label = clean_text(row['Label if different'] if 'Label if different' in columns and pd.notnull(row['Label if different']) else row['Question'], type='question_label')
    question_id = clean_text(cleaned_question_label, type='id')
    concept_id = row['External ID'] if 'External ID' in columns and pd.notnull(row['External ID']) else generate_external_id()
    
    concept_ids.add(concept_id)  # Add the concept ID to the set
    
    rendering = row['Datatype'].lower() if pd.notnull(row['Datatype']) else 'radio'
    validation_format = row['Validation (format)'] if 'Validation (format)' in columns and pd.notnull(row['Validation (format)']) else ''

    if rendering == 'coded' and validation_format == 'Multiple choice':
        rendering = 'radio'
    elif rendering == 'boolean':
        rendering = 'radio'

    question = {
        "label": cleaned_question_label,
        "type": "obs",  
        "required": str(row['Mandatory']).lower() == 'true' if 'Mandatory' in columns and pd.notnull(row['Mandatory']) else False,
        "id": question_id,
        "questionOptions": {
            "rendering": rendering,
            "concept": concept_id
        },
        "validators": safe_json_loads(row['Validation (format)']) if 'Validation (format)' in columns and pd.notnull(row['Validation (format)']) else []
    }
    
    if 'Default value' in columns and pd.notnull(row['Default value']):
        question['default'] = row['Default value']
    
    if 'Question' in columns and pd.notnull(row['Question']):
        question['questionInfo'] = row['Question']
        
    if 'Calculation' in columns and pd.notnull(row['Calculation']):
        question['questionOptions']['calculate'] = {"calculateExpression": row['Calculation']}
    
    if 'Skip logic' in columns and pd.notnull(row['Skip logic']):
        question['hide'] = {"hideWhenExpression": build_skip_logic_expression(row['Skip logic'])}
    
    if 'OptionSet name' in columns and pd.notnull(row['OptionSet name']):
        options = get_options(row['OptionSet name'])
        question['questionOptions']['answers'] = [
            {
                "label": clean_text(opt['Label if different'] if 'Label if different' in opt and pd.notnull(opt['Label if different']) else opt['Answers'], type='question_answer_label'),
                "concept": opt['External ID'] if 'External ID' in columns and pd.notnull(opt['External ID']) else generate_external_id()
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

# Function to check for missing concept IDs in calculations and skip logic expressions
def check_missing_concepts(forms, concept_ids):
    for form in forms:
        form_name = form["name"]
        missing_concepts = {}
        missing_ids = {}

        form_ids = {question["id"] for page in form["pages"] for section in page["sections"] for question in section["questions"]}

        for page in form["pages"]:
            for section in page["sections"]:
                for question in section["questions"]:
                    if 'questionOptions' in question:
                        if 'calculate' in question['questionOptions']:
                            calculation_concepts = re.findall(r"'([^']+)'", question['questionOptions']['calculate']['calculateExpression'])
                            for calc_concept in calculation_concepts:
                                if calc_concept not in concept_ids:
                                    missing_concepts[calc_concept] = question['label']
                        if 'hide' in question:
                            skip_logic_concepts = re.findall(r"'([^']+)'", question['hide']['hideWhenExpression'])
                            for skip_concept in skip_logic_concepts:
                                if skip_concept not in concept_ids:
                                    missing_concepts[skip_concept] = question['label']
                            skip_logic_ids = re.findall(r"\[([^\]]+)\]", question['hide']['hideWhenExpression'])
                            for skip_id in skip_logic_ids:
                                if skip_id not in form_ids:
                                    missing_ids[skip_id] = question['label']

        print(f"Form: {form_name}")
        if missing_concepts:
            print("  Missing concept IDs:")
            for concept, label in missing_concepts.items():
                print(f"    Concept ID '{concept}' not found, used in label '{label}'")
            print(f"  Total missing concept IDs: {len(missing_concepts)}")
        else:
            print("  No missing concept IDs found.")

        if missing_ids:
            print("  Missing IDs in skip logic:")
            for skip_id, label in missing_ids.items():
                print(f"    ID '{skip_id}' not found, used in label '{label}'")
            print(f"  Total missing IDs: {len(missing_ids)}")
        else:
            print("  No missing IDs in skip logic found.")
        print()

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

check_missing_concepts(all_forms, all_concept_ids)
print("Forms generation completed!")