
![Python Lint and Test](https://github.com/michaelbontyes/xlsx-to-O3-form-converter/actions/workflows/pylint.yml/badge.svg)

# XLSX to O3 Forms Converter

## Introduction
This Python script converts Excel files into JSON format for OpenMRS 3 forms.

## Requirements
- Python 3.x
- pandas
- openpyxl
- uuid
- json

## Installation
Clone this repository and navigate into the project directory:
```bash
# Clone the script
git clone https://github.com/michaelbontyes/xlsx-to-O3-form-converter
cd xlsx-to-O3-form-converter

# Run the script to generate the json file - specify the Xlsx and Json output in the script directly
py xlsx-to-O3-forms.py
```

## JSON Schema structure for O3 Form Engine

1. **Root Level**
   - name
   - description
   - version
   - published
   - retired
   - encounter
   - processor
   - referencedForms
   - uuid
   - pages (List)

2. **Pages**
   - Each page contains:
     - label
     - sections (List)

3. **Sections**
   - Each section contains:
     - label
     - isExpanded
     - questions (List)

4. **Questions**
   - Each question contains:
     - label
     - type
     - required
     - id
     - questionOptions
     - validators
     - hide (Optional)

5. **Question Options**
   - Each question option contains:
     - rendering
     - concept
     - conceptMappings
     - answers (List)

6. **Answers**
   - Each answer contains:
     - concept
     - label

