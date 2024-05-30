import pandas as pd
import json
import uuid
import re

def generate_id_from_label(label):
    return re.sub(r'\W+', '_', label).lower()

def parse_skip_logic(skip_logic):
    if pd.isna(skip_logic):
        return None
    match = re.match(r"Hide question if \[(.*?)\] <> '(.*?)'", skip_logic)
    if match:
        question, value = match.groups()
        return {
            "hide": {
                "hideWhenExpression": f"{generate_id_from_label(question)} !== '{value}'"
            }
        }
    return None

def xls_to_json(xls_file_path, json_file_path, form_schema):
    # Conversion table for rendering options
    rendering_conversion = {
        'Coded': 'radio',
        'Text': 'text',
        'Numeric': 'number',
        'Boolean': 'boolean',
        'Select': 'select',
        'MultiSelect': 'multiCheckbox',
        'Date': 'date'
    }

    # Read the XLS data from the specified sheet with the correct header
    df = pd.read_excel(xls_file_path, engine='openpyxl', sheet_name='F01-MHPSS_Baseline', header=1)
    optionsets_df = pd.read_excel(xls_file_path, engine='openpyxl', sheet_name='OptionSets', header=1, dtype=str)

    # Replace NaN with 'None' in the optionsets_df
    optionsets_df.fillna('None', inplace=True)

    # Create a dictionary for OptionSets
    optionsets_dict = {}
    for _, row in optionsets_df.iterrows():
        option_set_name = row['OptionSet name']
        option = row['Answers']
        if isinstance(option, str):
            option = re.sub(r'^\d+(\.\d+)?\s*|\.\s*', '', option)  # Remove leading numerotations and ". "
        if option_set_name not in optionsets_dict:
            optionsets_dict[option_set_name] = []
        optionsets_dict[option_set_name].append(option)

    # Transform XLS data into JSON structure
    form_name = 'F01-MHPSS_Baseline'
    json_data = {
        'name': form_name,
        'pages': [],
        'processor': form_schema['processor'],
        'encounterType': form_schema['encounterType'],
        'referencedForms': form_schema['referencedForms'],
        'uuid': str(uuid.uuid4()),  # Generate a new UUID
        'version': form_schema['version'],
        'description': form_name
    }
    current_page_label = None
    current_section_label = None
    questions_dict = {}  # To keep track of questions and nest answers

    # Process each row in the DataFrame
    for index, row in df.iterrows():
        # Skip empty or null questions
        if pd.isna(row['Question']):
            continue
        
        page_label = row['Page']
        section_label = row['Section']
        question_label = row['Label if different'] if pd.notna(row['Label if different']) else row['Question']
        required = row.get('Mandatory', False) == True
        question_id = generate_id_from_label(question_label)
        rendering = rendering_conversion.get(row['Datatype'], '')
        concept = row.get('Question', '')
        option_set_name = row.get('OptionSet name')
        skip_logic = parse_skip_logic(row.get('Skip logic'))

        # Check if we need to add a new page
        if page_label != current_page_label:
            current_page_label = page_label
            current_section_label = None
            json_data['pages'].append({
                'label': page_label,
                'sections': []
            })

        # Check if we need to add a new section
        if section_label != current_section_label:
            current_section_label = section_label
            json_data['pages'][-1]['sections'].append({
                'label': section_label,
                'isExpanded': False,
                'questions': []
            })

        # Set the rendering and answers accordingly
        question_options = {
            'rendering': rendering,
            'concept': concept,
            'conceptMappings': [],
            'answers': []
        }

        # Add answers from OptionSets if the question type is radio, select, or multiSelect and an OptionSet name is defined
        if rendering in ['radio', 'select', 'multiCheckbox'] and option_set_name in optionsets_dict:
            for option in optionsets_dict[option_set_name]:
                question_options['answers'].append({
                    'concept': option,
                    'label': option
                })
        elif rendering == 'boolean':
            question_options['answers'] = [
                {'concept': 'Yes', 'label': 'Yes'},
                {'concept': 'No', 'label': 'No'}
            ]

        # Create or update the question
        question = {
            'label': question_label,
            'type': 'obs',
            'required': required,
            'id': question_id,
            'questionOptions': question_options,
            'validators': []
        }

        # Add skip logic if defined
        if skip_logic:
            question.update(skip_logic)

        if question_id not in questions_dict:
            questions_dict[question_id] = question
            json_data['pages'][-1]['sections'][-1]['questions'].append(question)

    # Save the JSON data to a file
    with open(json_file_path, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)

# Load the form schema template
form_schema_path = 'O3_form_schema_template.json'
with open(form_schema_path, 'r') as file:
    form_schema = json.load(file)

# Example usage
xls_file_path = 'F01-MHPSS_Baseline.xlsx'
json_file_path = 'F01-MHPSS_Baseline.json'
xls_to_json(xls_file_path, json_file_path, form_schema)