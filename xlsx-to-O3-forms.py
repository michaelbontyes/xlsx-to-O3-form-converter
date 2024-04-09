import pandas as pd
import json
import uuid

def xls_to_json(xls_file_path, json_file_path):
    # Conversion table for rendering options
    rendering_conversion = {
        'Coded': 'radio',
        'Text': 'text',
        'Numeric': 'number',
        'Boolean': 'boolean'
    }

    # Read the XLS data from the specified sheet
    df = pd.read_excel(xls_file_path, engine='openpyxl', sheet_name='F01-MHPSS_Baseline')
    
    # Transform XLS data into JSON structure
    json_data = {
        'name': 'Page name',
        'pages': [],
        'processor': 'EncounterFormProcessor',
        'encounterType': 'dd528487-82a5-4082-9c72-ed246bd49591', # UUID of a Consultation encounter
        'referencedForms': [],
        'uuid': str(uuid.uuid4()),  # Generate a new UUID
        'version': '1.0'
    }
    current_page_label = None
    current_section_label = None
    questions_dict = {}  # To keep track of questions and nest answers

    # Process each row in the DataFrame
    for index, row in df.iterrows():
        page_label = row['Page'] # Use the page value from the XLSX file as the description
        json_data['description'] = page_label  
        json_data['name'] = page_label  
        section_label = row['Section']
        question_label = row['Question']
        required = row.get('Mandatory', False)  # Make "Required" optional
        question_id = row['Question ID']
        rendering = rendering_conversion.get(row['Datatype'], '')  # Use conversion table
        concept = row.get('Question', '')
        answer_concept = row.get('Answer', '')
        answer_label = row.get('Answer', '')

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
                'isExpanded': 'true',
                'questions': []
            })

        # Check if the datatype is "boolean" and set the rendering and answers accordingly
        if rendering == 'boolean':
            rendering = 'radio'
            question_options = {
                'rendering': rendering,
                'answers': [
                    {'concept': 'Yes', 'label': 'Yes'},
                    {'concept': 'No', 'label': 'No'}
                ]
            }
        else:
            rendering = rendering_conversion.get(row['Datatype'], '')  # Use conversion table
            question_options = {'rendering': rendering, 'answers': []}

        # Create or update the question
        if question_id not in questions_dict:
            question = {
                'label': question_label,
                'id': question_id,
                'questionOptions': question_options
            }
            if pd.notna(concept) and concept != '':
                question['questionOptions']['concept'] = concept
            if 'Required' in df.columns and pd.notna(row['Required']):
                question['required'] = row['Required']
            questions_dict[question_id] = question
            json_data['pages'][-1]['sections'][-1]['questions'].append(question)
        else:
            question = questions_dict[question_id]

        # Add answers if the question type is radio or coded
        if rendering in ['radio', 'coded'] and pd.notna(answer_concept) and answer_concept != '' and pd.notna(answer_label) and answer_label != '':
            question['questionOptions']['answers'].append({
                'concept': answer_concept,
                'label': answer_label
            })

    # Save the JSON data to a file
    with open(json_file_path, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)

# Example usage
xls_file_path = 'LIME EMR - Iraq Metadata - Release 1.xlsx'
json_file_path = 'F01-MHPSS_Baseline.json'
xls_to_json(xls_file_path, json_file_path)
